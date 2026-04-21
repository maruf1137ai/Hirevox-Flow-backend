import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.ai_service import gemini, prompts
from apps.common.mixins import CompanyScopedMixin
from apps.common.permissions import HasCompanyMembership

from .models import Job
from .serializers import GenerateJobSerializer, JobSerializer, PublicJobSerializer


logger = logging.getLogger("apps.jobs")


class JobViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = JobSerializer
    queryset = Job.objects.all()
    permission_classes = [IsAuthenticated, HasCompanyMembership]
    filterset_fields = ["status", "department"]
    search_fields = ["title", "department", "location"]
    ordering_fields = ["created_at", "published_at", "title"]

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.company,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        job = self.get_object()
        job.status = "active"
        job.published_at = timezone.now()
        job.save(update_fields=["status", "published_at", "updated_at"])
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        job = self.get_object()
        job.status = "paused"
        job.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        job = self.get_object()
        job.status = "closed"
        job.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"])
    def clone(self, request, pk=None):
        job = self.get_object()
        new_job = Job.objects.create(
            company=job.company,
            created_by=request.user,
            title=f"{job.title} (Clone)",
            department=job.department,
            location=job.location,
            seniority=job.seniority,
            employment_type=job.employment_type,
            salary_range=job.salary_range,
            summary=job.summary,
            responsibilities=job.responsibilities,
            requirements=job.requirements,
            nice_to_have=job.nice_to_have,
            skills=job.skills,
            rubric=job.rubric,
            screening_questions=job.screening_questions,
            status="draft",
        )
        return Response(self.get_serializer(new_job).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated, HasCompanyMembership])
def generate(request):
    """Take a 1-sentence prompt and return a fully drafted Job (not yet saved)."""
    serializer = GenerateJobSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    prompt_text = serializer.validated_data["prompt"]

    if not gemini.is_configured():
        return Response(
            {
                "detail": "AI is not configured. Add GEMINI_API_KEY to backend/.env.",
                "configured": False,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        company = request.company
        system = prompts.job_generator_system(company.name, company.tone)
        user_prompt = prompts.job_generator_user(prompt_text)
        draft = gemini.generate_json(user_prompt, system=system, mode="reasoning", temperature=0.4)
    except gemini.AIQuotaError as exc:
        logger.warning("Job generation quota exceeded: %s", exc)
        return Response(
            {"detail": "AI quota exceeded. Upgrade your Gemini plan or try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    except gemini.AIResponseError as exc:
        logger.warning("Job generation failed: %s", exc)
        return Response(
            {"detail": "AI couldn't generate a response. Try again."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    job = Job.objects.create(
        company=company,
        created_by=request.user,
        title=draft.get("title", "Untitled role"),
        seniority=draft.get("seniority", "") or "",
        location=draft.get("location", "") or "",
        employment_type=draft.get("employment_type", "full_time"),
        salary_range=draft.get("salary_range", ""),
        summary=draft.get("summary", ""),
        responsibilities=draft.get("responsibilities", []) or [],
        requirements=draft.get("requirements", []) or [],
        nice_to_have=draft.get("nice_to_have", []) or [],
        skills=draft.get("skills", []) or [],
        rubric=draft.get("rubric", []) or [],
        screening_questions=draft.get("screening_questions", []) or [],
        original_prompt=prompt_text,
        ai_generated=True,
        status="draft",
    )
    return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_list(request):
    """
    Search and list active jobs.
    Optional query params:
    - company: filter by company slug
    - search: keyword search in title/department
    """
    qs = Job.objects.filter(status="active").select_related("company")

    company_slug = request.query_params.get("company")
    if company_slug:
        qs = qs.filter(company__slug=company_slug)

    search = request.query_params.get("search")
    if search:
        qs = qs.filter(title__icontains=search) | qs.filter(department__icontains=search)

    qs = qs.order_by("-published_at")
    return Response(PublicJobSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_detail(request, slug):
    """Candidate-facing job detail page."""
    job = get_object_or_404(Job, public_slug=slug, status="active")
    return Response(PublicJobSerializer(job).data)
