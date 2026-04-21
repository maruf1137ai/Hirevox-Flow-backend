from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.candidates.models import Application
from apps.candidates.serializers import ApplicationSerializer
from apps.common.permissions import HasCompanyMembership
from apps.jobs.models import Job
from apps.jobs.serializers import JobSerializer

from . import services
from .models import WeeklyReport


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def overview(request):
    """Everything needed by the dashboard Overview page."""
    company = request.company

    stats = services.compute_overview_stats(company)
    funnel = services.compute_funnel(company)

    active_jobs = (
        Job.objects.filter(company=company, status="active")
        .order_by("-created_at")[:6]
    )
    top_candidates = (
        Application.objects.filter(company=company)
        .exclude(score__isnull=True)
        .select_related("candidate", "job")
        .order_by("-score")[:5]
    )

    # Activity feed — last 15 applications / stage changes.
    recent_applications = (
        Application.objects.filter(company=company)
        .select_related("candidate", "job")
        .order_by("-created_at")[:15]
    )
    activity = [
        {
            "who": app.candidate.name,
            "what": "submitted application for",
            "target": app.job.title,
            "at": app.created_at.isoformat(),
            "kind": "applied",
        }
        for app in recent_applications
    ]

    return Response({
        "stats": stats,
        "funnel": funnel,
        "active_jobs": JobSerializer(active_jobs, many=True).data,
        "top_candidates": ApplicationSerializer(top_candidates, many=True).data,
        "activity": activity,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def insights(request):
    """Latest weekly report + breakdowns for the Insights page."""
    company = request.company
    latest = WeeklyReport.objects.filter(company=company).order_by("-created_at").first()

    # Support period filter for sources/funnel: 7d, 30d, 90d (default: all time)
    period = request.query_params.get("period", "all")
    period_map = {"7d": 7, "30d": 30, "90d": 90}
    days = period_map.get(period)

    stats = services.compute_overview_stats(company)
    funnel = services.compute_funnel(company, days=days)
    sources = services.compute_sources(company, days=days)

    top_candidates = list(
        Application.objects.filter(company=company)
        .exclude(score__isnull=True)
        .select_related("candidate", "job")
        .order_by("-score")[:5]
        .values("candidate__name", "job__title", "score")
    )

    return Response({
        "report": {
            "id": str(latest.id) if latest else None,
            "headline": latest.headline if latest else None,
            "highlights": latest.highlights if latest else [],
            "insights": latest.insights if latest else [],
            "generated_at": latest.created_at.isoformat() if latest else None,
        } if latest else None,
        "stats": stats,
        "funnel": funnel,
        "sources": sources,
        "top_candidates": [
            {"name": c["candidate__name"], "role": c["job__title"], "score": c["score"]}
            for c in top_candidates
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def generate(request):
    result = services.generate_weekly_report(request.company, request.user)
    return Response(result)
