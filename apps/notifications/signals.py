"""Create notifications on key application events."""
from django.db.models.signals import post_save
from django.dispatch import receiver


def _notify_company_members(company, type_, title, body, data=None):
    from apps.accounts.models import Membership
    from .models import Notification

    members = Membership.objects.filter(company=company, is_active=True).select_related("user")
    Notification.objects.bulk_create([
        Notification(user=m.user, type=type_, title=title, body=body, data=data or {})
        for m in members
    ])


@receiver(post_save, sender="candidates.Application")
def on_application_save(sender, instance, created, **kwargs):
    if created:
        _notify_company_members(
            company=instance.company,
            type_="new_application",
            title="New application received",
            body=f"{instance.candidate.name} applied for {instance.job.title}.",
            data={"application_id": str(instance.id), "job_id": str(instance.job_id)},
        )
        return

    # Stage change notifications (only when stage actually changes)
    tracker_enabled = getattr(instance, "tracker_enabled", True)
    original_stage = getattr(instance, "_original_stage", None)

    if tracker_enabled and original_stage and instance.stage != original_stage:
        stage_labels = {
            "screening": "moved to AI Screening",
            "interview": "advanced to Interview",
            "offer": "reached Offer stage",
            "hired": "was marked as Hired",
            "rejected": "was rejected",
        }
        label = stage_labels.get(instance.stage)
        if label:
            _notify_company_members(
                company=instance.company,
                type_="stage_change",
                title=f"Candidate {label}",
                body=f"{instance.candidate.name} ({instance.job.title}) {label}.",
                data={"application_id": str(instance.id)},
            )


@receiver(post_save, sender="candidates.Application")
def on_score_ready(sender, instance, created, **kwargs):
    if created:
        return
    # Notify when score first set
    if instance.score is not None and not created:
        try:
            old = sender.objects.get(pk=instance.pk)
            if old.score is None:
                _notify_company_members(
                    company=instance.company,
                    type_="score_ready",
                    title="AI score ready",
                    body=f"{instance.candidate.name} scored {instance.score}/100 for {instance.job.title}.",
                    data={"application_id": str(instance.id)},
                )
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender="insights.WeeklyReport")
def on_report_ready(sender, instance, created, **kwargs):
    if not created:
        return
    _notify_company_members(
        company=instance.company,
        type_="ai_report",
        title="AI insights report ready",
        body=instance.headline or "Your weekly hiring intelligence report has been generated.",
        data={"report_id": str(instance.id)},
    )
