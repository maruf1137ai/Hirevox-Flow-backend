"""Core AI interview loop.

Public helpers:

- `start_session(application)` – greet the candidate; create messages; move app to screening.
- `reply(session, body)` – persist candidate message, produce AI follow-up, detect completion.
- `score_session(session)` – run the scorer once the interview completes and persist results.
"""

import logging
from typing import Any
from django.utils import timezone

from apps.ai_service import gemini, prompts
from apps.candidates.models import Application

from .models import InterviewMessage, InterviewSession

logger = logging.getLogger("apps.screening")

COMPLETION_TOKEN = "[INTERVIEW_COMPLETE]"


def _system_prompt_for(app: Application) -> str:
    return prompts.interview_system(
        job_title=app.job.title,
        skills=app.job.skills or [],
        rubric=app.job.rubric or [],
    )


def _history_for(session: InterviewSession) -> list[dict]:
    """Format message history in Gemini's expected shape."""
    return [
        {"role": m.gemini_role, "parts": [m.body]}
        for m in session.messages.all()
    ]


def start_session(application: Application) -> InterviewSession:
    """Initialize or resume a session. Emits the first AI greeting if none exists."""
    session, _ = InterviewSession.objects.get_or_create(application=application)

    if session.messages.exists():
        return session

    if application.stage == "applied":
        application.stage = "screening"
        application.save(update_fields=["stage", "updated_at"])

    session.status = "in_progress"
    session.started_at = timezone.now()

    if not gemini.is_configured():
        # Graceful fallback so the flow is usable without a key configured.
        fallback = (
            f"Hi {application.candidate.name.split()[0]}! Welcome to the screening "
            f"for the {application.job.title} role. I'll ask you a few questions "
            f"to learn about your experience. Let's start: tell me about a recent "
            f"project you're proud of."
        )
        InterviewMessage.objects.create(
            session=session, role="ai", gemini_role="model", body=fallback
        )
        session.turns_count = 1
        session.save(update_fields=["status", "started_at", "turns_count", "updated_at"])
        return session

    try:
        intro = gemini.generate_text(
            prompt=(
                f"Greet {application.candidate.name.split()[0]} warmly, explain "
                f"the format, and ask the first question. Keep it under 90 words."
            ),
            system=_system_prompt_for(application),
            temperature=0.7,
        )
    except gemini.AIConfigurationError:
        intro = "Hi there! Let's start the interview."
    except (gemini.AIResponseError, gemini.AIQuotaError) as exc:
        logger.warning("AI greeting failed: %s", exc)
        intro = "Hi! Let's start the interview. Tell me about a recent project you're proud of."

    InterviewMessage.objects.create(session=session, role="ai", gemini_role="model", body=intro)
    session.turns_count = 1
    session.save(update_fields=["status", "started_at", "turns_count", "updated_at"])
    return session


def reply(session: InterviewSession, body: str) -> dict:
    """Handle a candidate's turn. Returns dict {completed, message}."""
    if session.status == "completed":
        return {"completed": True, "message": None}

    # Persist candidate message
    InterviewMessage.objects.create(
        session=session, role="candidate", gemini_role="user", body=body
    )
    session.turns_count = session.messages.count()

    application = session.application

    if not gemini.is_configured():
        ai_text = (
            "Thanks for sharing. Could you walk me through a specific example, "
            "focusing on your decisions and what you'd do differently now?"
        )
    else:
        try:
            history = _history_for(session)
            ai_text = gemini.generate_text(
                prompt="Ask the next question (or wrap up with [INTERVIEW_COMPLETE] if enough signal).",
                system=_system_prompt_for(application),
                history=history,
                temperature=0.6,
            )
        except (gemini.AIResponseError, gemini.AIQuotaError) as exc:
            logger.warning("AI follow-up failed: %s", exc)
            ai_text = "Thanks. Could you give me a concrete example of that?"

    completed = COMPLETION_TOKEN in ai_text
    if completed:
        ai_text = ai_text.replace(COMPLETION_TOKEN, "").strip()

    ai_message = InterviewMessage.objects.create(
        session=session, role="ai", gemini_role="model", body=ai_text
    )
    session.turns_count = session.messages.count()

    if completed:
        session.status = "completed"
        session.completed_at = timezone.now()
        if application.stage == "screening":
            application.stage = "interview"
            application.save(update_fields=["stage", "updated_at"])

    session.save()

    if completed:
        try:
            score_session(session)
        except Exception as exc:
            logger.exception("Scoring failed: %s", exc)

    return {
        "completed": completed,
        "message": {
            "id": str(ai_message.id),
            "role": ai_message.role,
            "body": ai_message.body,
            "created_at": ai_message.created_at.isoformat(),
        },
    }


def voice_reply(session: InterviewSession, audio_file: Any) -> dict:
    """Handle a candidate's voice turn.
    
    1. Transcribe audio to text.
    2. Feed to standard reply logic.
    3. Synthesize AI response to audio.
    """
    import base64
    from apps.ai_service import gemini

    # 1. STT
    transcript = gemini.transcribe_audio(audio_file)

    # 2. Process Turn
    result = reply(session, transcript)

    # 3. TTS (Only if interview isn't immediately over or to have a goodbye message)
    # Even if completed, we want the AI to say its final goodbye.
    ai_text = result["message"]["body"]
    try:
        audio_bytes = gemini.generate_speech(ai_text)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as exc:
        logger.warning("TTS failed: %s", exc)
        audio_b64 = None

    return {
        **result,
        "transcript": transcript,  # Let frontend show what it "heard"
        "audio": audio_b64,        # Base64 encoded MP3
    }


def generate_cheatsheet(application: Application) -> dict:
    """Generate a recruiter 'cheat sheet' for the next live interview.

    Targets the candidate's lowest-scoring rubric criteria. Persists on the Application
    as ``interview_cheatsheet`` and returns the JSON payload.
    """
    import json

    rubric_scores = application.rubric_scores or []
    payload = {
        "job": {
            "title": application.job.title,
            "skills": application.job.skills or [],
            "rubric": application.job.rubric or [],
        },
        "candidate_name": application.candidate.name,
        "overall_score": application.score,
        "ai_summary": application.ai_summary,
        "strengths": application.strengths or [],
        "considerations": application.considerations or [],
        "rubric_scores": rubric_scores,
    }

    if not gemini.is_configured() or not rubric_scores:
        # Deterministic fallback so the UI still renders something useful.
        weakest = sorted(rubric_scores, key=lambda r: r.get("score", 100))[:3]
        fallback_questions = [
            {
                "question": f"Walk me through a concrete example of your work in {r.get('criterion', 'this area')}.",
                "focus": r.get("criterion", "—"),
                "rationale": r.get("evidence") or "Screening evidence was thin; probe live.",
                "tip": "A strong answer cites specifics (numbers, tradeoffs, outcomes). Watch for hand-waving.",
            }
            for r in weakest
        ] or [{
            "question": "Tell me about a recent project you're most proud of and what you'd do differently.",
            "focus": "General",
            "rationale": "AI scoring unavailable — use this as a baseline opener.",
            "tip": "Press for specifics: scope, decisions, outcome.",
        }]
        data = {
            "focus_areas": [r.get("criterion", "—") for r in weakest] or ["General"],
            "summary": "AI cheat sheet unavailable — baseline probes targeting weak areas.",
            "questions": fallback_questions,
        }
    else:
        prompt = (
            "Generate a recruiter cheat sheet for the live follow-up interview. "
            "Target the lowest-scoring rubric criteria. Return strict JSON.\n\n"
            f"{json.dumps(payload, default=str)}"
        )
        try:
            data = gemini.generate_json(
                prompt,
                system=prompts.cheatsheet_system(),
                mode="reasoning",
                temperature=0.4,
            )
        except (gemini.AIResponseError, gemini.AIQuotaError) as exc:
            logger.warning("Cheat sheet AI failed: %s", exc)
            data = {
                "focus_areas": [],
                "summary": "Cheat sheet generation failed — try again in a moment.",
                "questions": [],
            }

    data["generated_at"] = timezone.now().isoformat()
    application.interview_cheatsheet = data
    application.save(update_fields=["interview_cheatsheet", "updated_at"])
    return data


def score_session(session: InterviewSession) -> dict:
    """Score a completed session and persist results on the Application."""
    app = session.application

    transcript = "\n".join(
        f"{'AI' if m.role == 'ai' else app.candidate.name}: {m.body}"
        for m in session.messages.all()
    )

    payload = {
        "job": {
            "title": app.job.title,
            "skills": app.job.skills,
            "rubric": app.job.rubric,
        },
        "candidate_name": app.candidate.name,
        "transcript": transcript,
    }

    import json
    prompt = (
        "Score this candidate against the rubric. Be fair, cite evidence from the "
        "transcript, return strict JSON per the schema.\n\n"
        f"{json.dumps(payload)}"
    )

    if not gemini.is_configured():
        # Deterministic fallback score so the UI still renders without Gemini.
        rubric = app.job.rubric or []
        fallback_rubric = [
            {
                "criterion": r.get("criterion", "Criterion"),
                "score": 70,
                "evidence": "AI scoring unavailable (no GEMINI_API_KEY).",
                "reasoning": "Fallback baseline.",
            }
            for r in rubric
        ] or [{"criterion": "Overall", "score": 70, "evidence": "", "reasoning": ""}]
        app.score = 70
        app.ai_summary = "AI scoring is unavailable until GEMINI_API_KEY is set."
        app.strengths = []
        app.considerations = ["AI scoring disabled — add GEMINI_API_KEY to enable."]
        app.rubric_scores = fallback_rubric
        app.status = "review"
        app.save()
        return {"overall_score": 70, "status": "review"}

    try:
        result = gemini.generate_json(prompt, system=prompts.scoring_system(), mode="reasoning", temperature=0.3)
    except (gemini.AIResponseError, gemini.AIQuotaError) as exc:
        logger.warning("Scoring AI failed: %s", exc)
        return {}

    app.score = int(result.get("overall_score", 0))
    app.ai_summary = result.get("summary", "")
    app.strengths = result.get("strengths", []) or []
    app.considerations = result.get("considerations", []) or []
    app.rubric_scores = result.get("rubric_scores", []) or []

    status_map = {"recommended", "shortlist", "review", "rejected"}
    app.status = result.get("status") if result.get("status") in status_map else "review"

    app.save()
    return result
