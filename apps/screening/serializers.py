from rest_framework import serializers

from .models import InterviewMessage, InterviewSession


class InterviewMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewMessage
        fields = ("id", "role", "body", "created_at")
        read_only_fields = ("id", "role", "created_at")


class InterviewSessionSerializer(serializers.ModelSerializer):
    messages = InterviewMessageSerializer(many=True, read_only=True)
    job_title = serializers.CharField(source="application.job.title", read_only=True)
    candidate_name = serializers.CharField(source="application.candidate.name", read_only=True)

    class Meta:
        model = InterviewSession
        fields = (
            "id", "status", "started_at", "completed_at", "turns_count",
            "job_title", "candidate_name", "messages", "created_at",
        )


class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=1, max_length=4000)


class StartSessionSerializer(serializers.Serializer):
    access_token = serializers.CharField(max_length=80)
