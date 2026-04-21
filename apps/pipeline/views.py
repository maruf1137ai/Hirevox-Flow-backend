from collections import defaultdict

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.candidates.models import Application
from apps.candidates.serializers import ApplicationSerializer
from apps.common.permissions import HasCompanyMembership

from .models import StageTransition

STAGES = ["applied", "screening", "interview", "offer", "hired"]

STAGE_ACCENTS = {
    "applied": "bg-slate-400",
    "screening": "bg-indigo-400",
    "interview": "bg-violet-500",
    "offer": "bg-emerald-500",
    "hired": "bg-emerald-700",
}

STAGE_LABELS = {
    "applied": "Applied",
    "screening": "Screening",
    "interview": "Interview",
    "offer": "Offer",
    "hired": "Hired",
}


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def board(request):
    """Kanban board payload: all active applications grouped by stage."""
    job_id = request.GET.get("job")
    qs = Application.objects.filter(company=request.company).select_related("candidate", "job")
    if job_id:
        qs = qs.filter(job_id=job_id)
    qs = qs.exclude(stage="rejected")

    grouped = defaultdict(list)
    for app in qs.order_by("-score", "-created_at"):
        grouped[app.stage].append(ApplicationSerializer(app).data)

    columns = [
        {
            "id": stage,
            "title": STAGE_LABELS[stage],
            "accent": STAGE_ACCENTS[stage],
            "count": len(grouped[stage]),
            "cards": grouped[stage],
        }
        for stage in STAGES
    ]
    return Response({"columns": columns})


@api_view(["POST"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def move(request):
    """Move an application to a new stage."""
    application_id = request.data.get("application_id")
    to_stage = request.data.get("to_stage")

    if not application_id or not to_stage:
        return Response(
            {"detail": "application_id and to_stage are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if to_stage not in STAGES + ["rejected"]:
        return Response(
            {"detail": f"Unknown stage: {to_stage}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    app = get_object_or_404(Application, id=application_id, company=request.company)
    from_stage = app.stage

    if from_stage == to_stage:
        return Response(ApplicationSerializer(app).data)

    app.stage = to_stage
    if to_stage == "rejected":
        app.status = "rejected"
    app.save()

    StageTransition.objects.create(
        application=app,
        from_stage=from_stage,
        to_stage=to_stage,
        moved_by=request.user,
        reason=request.data.get("reason", ""),
    )

    return Response(ApplicationSerializer(app).data)
