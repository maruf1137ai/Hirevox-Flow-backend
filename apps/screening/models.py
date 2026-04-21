from django.db import models

from apps.common.models import TimestampedModel


class InterviewSession(TimestampedModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("abandoned", "Abandoned"),
    ]

    application = models.OneToOneField(
        "candidates.Application",
        on_delete=models.CASCADE,
        related_name="session",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    turns_count = models.IntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Session for {self.application}"


class InterviewMessage(TimestampedModel):
    ROLE_CHOICES = [
        ("ai", "AI"),
        ("candidate", "Candidate"),
    ]

    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    body = models.TextField()
    # Maps role → Gemini history format ({"role": "user"|"model", "parts": [str]})
    gemini_role = models.CharField(max_length=20)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.role}: {self.body[:60]}"
