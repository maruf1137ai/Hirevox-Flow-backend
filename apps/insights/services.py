"""Compute dashboard stats + generate AI weekly report."""

import logging
from datetime import timedelta

logger = logging.getLogger("apps.insights")

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.ai_service import gemini, prompts
from apps.candidates.models import Application
from apps.jobs.models import Job


def compute_overview_stats(company) -> dict:
    """The numbers on the dashboard Overview page."""
    now = timezone.now()
    last_7 = now - timedelta(days=7)
    prev_7 = now - timedelta(days=14)

    active_jobs = Job.objects.filter(company=company, status="active").count()
    total_applications = Application.objects.filter(company=company).count()
    pipeline = Application.objects.filter(company=company).exclude(stage__in=["rejected", "hired"]).count()

    new_last_7 = Application.objects.filter(company=company, created_at__gte=last_7).count()
    new_prev_7 = Application.objects.filter(
        company=company, created_at__gte=prev_7, created_at__lt=last_7
    ).count()

    # Pass-through = candidates who passed screening rubric (status recommended or shortlist)
    passed = Application.objects.filter(
        company=company, status__in=["recommended", "shortlist"]
    ).count()
    pass_through = int(passed / total_applications * 100) if total_applications else 0

    return {
        "active_jobs": active_jobs,
        "pipeline_count": pipeline,
        "new_applications_7d": new_last_7,
        "delta_applications": new_last_7 - new_prev_7,
        "pass_through_rate": pass_through,
        "total_applications": total_applications,
    }


def compute_funnel(company, days=None) -> list[dict]:
    base_qs = Application.objects.filter(company=company)
    if days:
        cutoff = timezone.now() - timedelta(days=days)
        base_qs = base_qs.filter(created_at__gte=cutoff)

    total = base_qs.count()
    if total == 0:
        return []

    def pct(v: int) -> float:
        return round(v / total * 100, 1)

    stages = [
        ("applied", "Applications", base_qs.count()),
        ("screened", "AI screened",
         base_qs.filter(Q(stage="screening") | Q(stage="interview") | Q(stage="offer") | Q(stage="hired")).count()),
        ("passed", "Passed rubric",
         base_qs.filter(status__in=["recommended", "shortlist"]).count()),
        ("interview", "Interviewed",
         base_qs.filter(stage__in=["interview", "offer", "hired"]).count()),
        ("offer", "Offers",
         base_qs.filter(stage__in=["offer", "hired"]).count()),
        ("hired", "Hired",
         base_qs.filter(stage="hired").count()),
    ]
    return [{"key": k, "label": l, "value": v, "pct": pct(v)} for k, l, v in stages]


def compute_sources(company, days=None) -> list[dict]:
    qs = Application.objects.filter(company=company)
    if days:
        cutoff = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=cutoff)

    qs = (
        qs.values("source")
        .annotate(total=Count("id"), hired=Count("id", filter=Q(stage="hired")))
    )
    out = []
    for row in qs:
        total = row["total"] or 0
        hired = row["hired"] or 0
        rate = round(hired / total * 100, 1) if total else 0.0
        out.append({
            "source": row["source"],
            "applications": total,
            "hires": hired,
            "rate": f"{rate}%",
        })
    return sorted(out, key=lambda r: r["applications"], reverse=True)


def generate_weekly_report(company, user) -> dict:
    """Ask Gemini to summarize the last 7 days. Persists a WeeklyReport row."""
    from .models import WeeklyReport

    stats = compute_overview_stats(company)
    funnel = compute_funnel(company)
    sources = compute_sources(company)

    # Gather concrete things for the prompt
    top_candidates = list(
        Application.objects.filter(company=company)
        .exclude(score__isnull=True)
        .order_by("-score")
        .select_related("candidate", "job")[:5]
        .values("candidate__name", "job__title", "score", "status")
    )
    open_jobs = list(
        Job.objects.filter(company=company, status="active")
        .order_by("-created_at")
        .values("title", "department", "created_at")[:10]
    )

    context = {
        "company": company.name,
        "stats": stats,
        "funnel": funnel,
        "sources": sources,
        "top_candidates": [
            {"name": c["candidate__name"], "role": c["job__title"], "score": c["score"], "status": c["status"]}
            for c in top_candidates
        ],
        "open_jobs": [
            {"title": j["title"], "department": j["department"], "days_open": (timezone.now() - j["created_at"]).days}
            for j in open_jobs
        ],
    }

    if not gemini.is_configured():
        # Deterministic fallback so the Insights page renders without a key.
        report_data = {
            "headline": f"{stats['new_applications_7d']} new applications this week, {stats['active_jobs']} active roles.",
            "highlights": [
                f"{len(top_candidates)} top candidates scored above 80.",
                f"Pass-through rate is {stats['pass_through_rate']}%.",
            ],
            "insights": [
                {
                    "type": "pattern",
                    "title": "AI insights unavailable",
                    "body": "Add GEMINI_API_KEY to backend/.env to enable AI-generated insights.",
                    "priority": "low",
                    "action": None,
                }
            ],
        }
    else:
        import json
        try:
            report_data = gemini.generate_json(
                f"Weekly data:\n{json.dumps(context, default=str)}",
                system=prompts.insights_system(),
                mode="reasoning",
                temperature=0.5,
            )
        except (gemini.AIResponseError, gemini.AIQuotaError) as exc:
            logger.warning("Insights AI failed: %s", exc)
            report_data = {
                "headline": "Weekly snapshot unavailable.",
                "highlights": [],
                "insights": [],
            }

    report = WeeklyReport.objects.create(
        company=company,
        generated_by=user,
        headline=report_data.get("headline", ""),
        highlights=report_data.get("highlights", []) or [],
        insights=report_data.get("insights", []) or [],
        stats_snapshot={"stats": stats, "funnel": funnel, "sources": sources},
    )
    return {
        "id": str(report.id),
        "headline": report.headline,
        "highlights": report.highlights,
        "insights": report.insights,
        "generated_at": report.created_at.isoformat(),
        "stats": stats,
        "funnel": funnel,
        "sources": sources,
        "top_candidates": context["top_candidates"],
    }
