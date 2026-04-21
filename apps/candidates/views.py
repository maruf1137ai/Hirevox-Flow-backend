import csv
from django.conf import settings
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.mixins import CompanyScopedMixin
from apps.common.permissions import HasCompanyMembership
from apps.jobs.models import Job

from .models import Application, Candidate, Note, Message
from .serializers import (
    ApplicationDetailSerializer,
    ApplicationSerializer,
    CandidateSerializer,
    MessageSerializer,
    NoteSerializer,
    PublicApplySerializer,
)


class ApplicationViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Application.objects.select_related("candidate", "job").prefetch_related("notes__author")
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, HasCompanyMembership]
    filterset_fields = ["stage", "status", "job", "source"]
    search_fields = ["candidate__name", "candidate__email", "candidate__current_company"]
    ordering_fields = ["score", "created_at"]
    ordering = ["-score", "-created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ApplicationDetailSerializer
        return ApplicationSerializer

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        """Move the application one stage forward."""
        app = self.get_object()
        order = ["applied", "screening", "interview", "offer", "hired"]
        if app.stage not in order:
            return Response({"detail": "Cannot advance from this stage."}, status=400)
        idx = order.index(app.stage)
        if idx == len(order) - 1:
            return Response({"detail": "Already at final stage."}, status=400)
        app.stage = order[idx + 1]
        app.save(update_fields=["stage", "updated_at"])
        return Response(ApplicationDetailSerializer(app).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        app = self.get_object()
        app.stage = "rejected"
        app.status = "rejected"
        app.save(update_fields=["stage", "status", "updated_at"])
        return Response(ApplicationDetailSerializer(app).data)

    @action(detail=True, methods=["post"], url_path="notes")
    def add_note(self, request, pk=None):
        app = self.get_object()
        body = (request.data or {}).get("body", "").strip()
        if not body:
            return Response({"detail": "Note body is required."}, status=400)
        note = Note.objects.create(application=app, author=request.user, body=body)
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="messages")
    def send_message(self, request, pk=None):
        app = self.get_object()
        data = request.data or {}

        message_type = data.get("message_type", "chat")
        body = data.get("body", "").strip()
        subject = data.get("subject", "").strip()

        if not body:
            return Response({"detail": "Message body is required."}, status=400)

        message = Message.objects.create(
            application=app,
            sender_type="recruiter",
            message_type=message_type,
            subject=subject,
            body=body,
            author=request.user
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cheatsheet")
    def cheatsheet(self, request, pk=None):
        """Generate an interviewer cheat sheet targeting this candidate's weakest areas."""
        from apps.screening.services import generate_cheatsheet
        app = self.get_object()
        data = generate_cheatsheet(app)
        return Response(data)

    @action(detail=True, methods=["post"], url_path="draft-email")
    def draft_email(self, request, pk=None):
        """Draft a professional, personalized email for the candidate."""
        from apps.ai_service import gemini as ai_service
        app = self.get_object()
        subject = (request.data or {}).get("subject", "").strip() or f"Update regarding your {app.job_title} application"

        # Build intelligent context
        candidate = app.candidate
        job = app.job
        recruiter_name = getattr(request.user, "name", "") or request.user.email
        recruiter_title = getattr(request.user, "title", "Recruiter")
        company_label = request.company.name if getattr(request, "company", None) else "Hirevox Team"

        system_prompt = (
            "You are an elite executive tech recruiter at Hirevox. Your goal is to write high-quality, "
            "persuasive, and professional emails to top-tier candidates. The tone should be "
            "warm, professional, and sophisticated."
        )

        user_prompt = f"""
        Draft a high-quality professional email to the following candidate:

        Candidate Name: {candidate.name}
        Current Role: {candidate.current_role} at {candidate.current_company}
        Position applied for: {job.title if job else 'the open position'}

        Technical Highlights: 
        {", ".join(app.strengths) if app.strengths else "Experienced professional"}

        Selection Considerations: 
        {", ".join(app.considerations) if app.considerations else "General intake"}

        Requested Subject: {subject}
        Recruiter (Sign-off): {recruiter_name}, {recruiter_title} from {company_label}

        Requirements:
        1. Start with a tailored opening that acknowledges their background.
        2. Reference why their specific skill set caught our eye.
        3. Be concise and impactful—no corporate fluff.
        4. End with an invitation to view their status on the progress portal.
        5. Sign off professionally with {recruiter_name}, {recruiter_title} and {company_label}.
        6. Return ONLY the body text.
        """

        try:
            body = ai_service.generate_text(user_prompt, system=system_prompt)
            return Response({"body": body})
        except Exception as e:
            return Response({"detail": f"AI Generation failed: {str(e)}"}, status=500)

    @action(detail=True, methods=["post"], url_path="ai-discuss")
    def ai_discuss(self, request, pk=None):
        """AI Advisor: discuss this candidate & job with the recruiter."""
        from apps.ai_service import gemini as ai_service
        app = self.get_object()
        data = request.data or {}
        message = data.get("message", "").strip()
        history = data.get("history", [])

        if not message:
            return Response({"detail": "Message is required."}, status=400)

        candidate = app.candidate
        job = app.job
        recruiter_name = getattr(request.user, "name", "") or request.user.email
        company_label = request.company.name if getattr(request, "company", None) else "your company"

        system_prompt = f"""You are an expert AI hiring advisor for {recruiter_name} at {company_label}.

=== CANDIDATE ===
Name: {candidate.name}
Email: {candidate.email}
Current Role: {candidate.current_role or "N/A"} at {candidate.current_company or "N/A"}
Location: {candidate.location or "N/A"}
Tags: {", ".join(candidate.tags or []) or "N/A"}
LinkedIn: {candidate.linkedin_url or "N/A"}
GitHub: {candidate.github_url or "N/A"}
External Profile Summary: {(candidate.external_intelligence or {}).get("overall_summary", "N/A")}
Tech Stack (detected): {", ".join((candidate.external_intelligence or {}).get("tech_stack", [])) or "N/A"}

=== APPLICATION ===
Job: {job.title if job else "N/A"} ({job.department or "N/A" if job else ""})
Stage: {app.stage} | Status: {app.status} | AI Score: {app.score or "N/A"}/100
Summary: {app.ai_summary or "N/A"}
Strengths: {", ".join(app.strengths or []) or "N/A"}
Considerations: {", ".join(app.considerations or []) or "N/A"}

=== JOB REQUIREMENTS ===
{chr(10).join(job.requirements or []) if job and job.requirements else "N/A"}
Skills needed: {", ".join(job.skills or []) if job and job.skills else "N/A"}

Give concise, direct, expert hiring advice. Answer questions about candidate fit, suggest interview questions, flag risks."""

        turns = [{"role": h["role"], "content": h["content"]} for h in history if h.get("role") in ("user", "assistant")]
        turns.append({"role": "user", "content": message})
        context_prompt = "\n\n".join(
            f"{'Recruiter' if t['role'] == 'user' else 'Advisor'}: {t['content']}" for t in turns
        )

        try:
            reply = ai_service.generate_text(context_prompt, system=system_prompt)
            return Response({"reply": reply})
        except Exception as e:
            return Response({"detail": f"AI failed: {str(e)}"}, status=500)

@api_view(["POST"])
@permission_classes([AllowAny])
def public_apply(request, slug):
    """Accept a candidate's application to a published job.

    Creates/updates Candidate + creates Application. Returns the access_token
    the candidate will use to start their AI interview.
    """
    job = get_object_or_404(Job, public_slug=slug, status="active")

    serializer = PublicApplySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    with transaction.atomic():
        candidate, _created = Candidate.objects.get_or_create(
            company=job.company,
            email=data["email"].lower(),
            defaults={
                "name": data["name"],
                "phone": data.get("phone", ""),
                "location": data.get("location", ""),
                "current_role": data.get("current_role", ""),
                "current_company": data.get("current_company", ""),
                "linkedin_url": data.get("linkedin_url", ""),
                "github_url": data.get("github_url", ""),
                "portfolio_url": data.get("portfolio_url", ""),
            },
        )
        # Refresh mutable fields on re-apply.
        for field in ("name", "phone", "location", "current_role", "current_company",
                      "linkedin_url", "github_url", "portfolio_url"):
            if data.get(field):
                setattr(candidate, field, data[field])
        candidate.save()

        # Trigger background analysis of online presence
        from .intelligence import analyze_candidate_online_presence
        import threading
        threading.Thread(target=analyze_candidate_online_presence, args=(candidate,), daemon=True).start()

        app, app_created = Application.objects.get_or_create(
            candidate=candidate,
            job=job,
            defaults={
                "company": job.company,
                "stage": "applied",
                "status": "review",
                "source": data.get("source", "direct"),
            },
        )

    return Response({
        "application_id": str(app.id),
        "access_token": app.access_token,
        "interview_url": f"{settings.WEBSITE_URL}/interview/{app.access_token}",
        "already_applied": not app_created,
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def application_progress(request, token):
    """View application stage and communication history."""
    app = get_object_or_404(Application.objects.select_related("candidate", "job"), access_token=token)
    messages = app.messages.all().order_by("created_at")

    return Response({
        "application": {
            "id": app.id,
            "job_title": app.job.title,
            "stage": app.stage,
            "status": app.status,
            "candidate_name": app.candidate.name,
        },
        "messages": MessageSerializer(messages, many=True).data
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def candidate_reply(request, token):
    """Allow a candidate to reply to a chat thread."""
    app = get_object_or_404(Application, access_token=token)
    body = (request.data or {}).get("body", "").strip()
    if not body:
        return Response({"detail": "Message body is required."}, status=400)

    message = Message.objects.create(
        application=app,
        sender_type="candidate",
        message_type="chat",
        body=body
    )
    return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def export_csv(request):
    """Export all applications for the company as CSV."""
    from apps.common.permissions import HasCompanyMembership
    company = request.company

    qs = Application.objects.filter(company=company).select_related("candidate", "job").order_by("-created_at")

    # Optional filters
    stage = request.query_params.get("stage")
    status_filter = request.query_params.get("status")
    if stage:
        qs = qs.filter(stage=stage)
    if status_filter:
        qs = qs.filter(status=status_filter)

    def rows():
        yield ["Name", "Email", "Phone", "Location", "Current Role", "Current Company",
               "Job Title", "Stage", "Status", "AI Score", "Source", "Applied At"]
        for app in qs:
            c = app.candidate
            yield [
                c.name, c.email, c.phone or "", c.location or "",
                c.current_role or "", c.current_company or "",
                app.job.title, app.stage, app.status,
                app.score if app.score is not None else "",
                app.source,
                app.created_at.strftime("%Y-%m-%d %H:%M"),
            ]

    def stream():
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in rows():
            writer.writerow(row)
            yield buf.getvalue()
            buf.truncate(0)
            buf.seek(0)

    filename = f"candidates_{company.slug}_{timezone.now().strftime('%Y%m%d')}.csv"
    response = StreamingHttpResponse(stream(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_applications(request):
    """List all applications for the authenticated candidate (across all companies)."""
    email = request.user.email
    applications = Application.objects.filter(candidate__email__iexact=email).select_related("job", "company").order_by("-created_at")
    
    # We can use the simple ApplicationSerializer or a specialized one
    data = []
    for app in applications:
        data.append({
            "id": app.id,
            "job_title": app.job.title,
            "company_name": app.company.name,
            "stage": app.stage,
            "status": app.status,
            "score": app.score,
            "created_at": app.created_at,
            "access_token": app.access_token,
        })
    
    return Response(data)
