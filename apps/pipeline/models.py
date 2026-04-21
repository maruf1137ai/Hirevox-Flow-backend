from django.db import models

from apps.common.models import TimestampedModel


class StageTransition(TimestampedModel):
    """Audit log for pipeline moves — useful for analytics + undo."""

    application = models.ForeignKey(
        "candidates.Application",
        on_delete=models.CASCADE,
        related_name="transitions",
    )
    from_stage = models.CharField(max_length=20)
    to_stage = models.CharField(max_length=20)
    moved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="stage_transitions",
    )
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
