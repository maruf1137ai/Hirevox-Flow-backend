from rest_framework import serializers

from apps.jobs.models import Job

from .models import Application, Candidate, Note, Message


class CandidateSerializer(serializers.ModelSerializer):
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = Candidate
        fields = (
            "id", "name", "email", "phone", "location", "initials",
            "current_role", "current_company",
            "linkedin_url", "github_url", "portfolio_url",
            "tags", "external_intelligence", "created_at",
        )
        read_only_fields = ("id", "initials", "created_at")


class NoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)
    author_initials = serializers.CharField(source="author.initials", read_only=True)

    class Meta:
        model = Note
        fields = ("id", "body", "author_name", "author_initials", "created_at")
        read_only_fields = ("id", "author_name", "author_initials", "created_at")


class MessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)

    class Meta:
        model = Message
        fields = (
            "id", "sender_type", "message_type", "subject", "body",
            "is_read", "author_name", "created_at"
        )
        read_only_fields = ("id", "author_name", "created_at")


class ApplicationSerializer(serializers.ModelSerializer):
    candidate = CandidateSerializer(read_only=True)
    job_title = serializers.CharField(source="job.title", read_only=True)
    job_id = serializers.UUIDField(source="job.id", read_only=True)

    class Meta:
        model = Application
        fields = (
            "id", "candidate", "job_id", "job_title",
            "stage", "status", "source",
            "score", "ai_summary", "strengths", "considerations", "rubric_scores",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "candidate", "job_id", "job_title",
            "score", "ai_summary", "strengths", "considerations", "rubric_scores",
            "created_at", "updated_at",
        )


class ApplicationDetailSerializer(ApplicationSerializer):
    notes = NoteSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    access_token = serializers.CharField(read_only=True)
    interview_cheatsheet = serializers.SerializerMethodField()

    class Meta(ApplicationSerializer.Meta):
        fields = ApplicationSerializer.Meta.fields + ("notes", "messages", "access_token", "interview_cheatsheet")

    def get_interview_cheatsheet(self, obj):
        data = obj.interview_cheatsheet
        if not data or not isinstance(data, dict) or not data.get("questions"):
            return None
        return data


class PublicApplySerializer(serializers.Serializer):
    """What a candidate submits on the public apply page."""

    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    location = serializers.CharField(max_length=200, required=False, allow_blank=True)
    current_role = serializers.CharField(max_length=200, required=False, allow_blank=True)
    current_company = serializers.CharField(max_length=200, required=False, allow_blank=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)
    github_url = serializers.URLField(required=False, allow_blank=True)
    portfolio_url = serializers.URLField(required=False, allow_blank=True)
    source = serializers.ChoiceField(choices=Application.SOURCE_CHOICES, required=False, default="direct")
