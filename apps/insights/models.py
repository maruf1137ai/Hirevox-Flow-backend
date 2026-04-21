from django.db import models

from apps.common.models import TimestampedModel


class WeeklyReport(TimestampedModel):
    company = models.ForeignKey("accounts.Company", on_delete=models.CASCADE, related_name="weekly_reports")
    generated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_reports",
    )

    headline = models.TextField()
    highlights = models.JSONField(default=list, blank=True)
    insights = models.JSONField(default=list, blank=True)  # [{type, title, body, priority, action}]
    # Snapshotted stats at generation time (so report is reproducible).
    stats_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Weekly report for {self.company.name} on {self.created_at.date()}"
