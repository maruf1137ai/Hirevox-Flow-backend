from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import HasCompanyMembership


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({
        "status": "ok",
        "ai_configured": bool(settings.OPENAI_API_KEY or settings.GEMINI_API_KEY),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ping(request):
    return Response({
        "user_id": str(request.user.id),
        "email": request.user.email,
        "company_id": str(request.company.id) if request.company else None,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def search(request):
    """Global search across jobs and candidates for the active company."""
    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return Response({"jobs": [], "candidates": []})

    company = request.company

    from apps.jobs.models import Job
    from apps.candidates.models import Application

    jobs = Job.objects.filter(
        company=company,
        status__in=["active", "draft", "paused"],
    ).filter(
        Q(title__icontains=q) | Q(department__icontains=q) | Q(location__icontains=q)
    )[:8]

    apps = Application.objects.filter(company=company).select_related("candidate", "job").filter(
        Q(candidate__name__icontains=q) |
        Q(candidate__email__icontains=q) |
        Q(candidate__current_role__icontains=q) |
        Q(candidate__current_company__icontains=q) |
        Q(job__title__icontains=q)
    )[:8]

    return Response({
        "jobs": [
            {"id": str(j.id), "title": j.title, "department": j.department,
             "location": j.location, "status": j.status}
            for j in jobs
        ],
        "candidates": [
            {
                "id": str(a.id),
                "name": a.candidate.name,
                "email": a.candidate.email,
                "current_role": a.candidate.current_role,
                "job_title": a.job.title,
                "stage": a.stage,
                "score": a.score,
            }
            for a in apps
        ],
    })
