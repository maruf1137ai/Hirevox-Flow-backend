from rest_framework import serializers

from .models import Job


class JobSerializer(serializers.ModelSerializer):
    counts = serializers.ReadOnlyField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = (
            "id", "public_slug", "public_url",
            "title", "department", "location", "seniority", "employment_type",
            "salary_range", "summary", "responsibilities", "requirements",
            "nice_to_have", "skills", "rubric", "screening_questions",
            "original_prompt", "ai_generated", "status", "published_at",
            "counts", "created_at", "updated_at",
        )
        read_only_fields = ("id", "public_slug", "public_url", "counts", "created_at", "updated_at")

    def get_public_url(self, obj) -> str:
        from django.conf import settings
        return f"{settings.WEBSITE_URL}/apply/{obj.public_slug}"


class PublicJobSerializer(serializers.ModelSerializer):
    """Exposed publicly on the apply page — strip anything candidates shouldn't see."""

    company_name = serializers.CharField(source="company.name", read_only=True)
    company_logo = serializers.URLField(source="company.logo_url", read_only=True)

    class Meta:
        model = Job
        fields = (
            "public_slug", "title", "department", "location", "seniority",
            "employment_type", "salary_range", "summary", "responsibilities",
            "requirements", "nice_to_have", "skills",
            "company_name", "company_logo", "published_at",
        )


class GenerateJobSerializer(serializers.Serializer):
    prompt = serializers.CharField(min_length=10, max_length=2000)
