import uuid
from django.db import models
from apps.accounts.models import User


NOTIFICATION_TYPES = [
    ("new_application", "New Application"),
    ("stage_change", "Stage Changed"),
    ("score_ready", "AI Score Ready"),
    ("ai_report", "AI Report Ready"),
    ("offer_response", "Offer Response"),
]


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.title}"
