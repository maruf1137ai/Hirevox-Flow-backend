import secrets
from django.db import models
from django.utils.text import slugify

from apps.common.models import TimestampedModel


class Job(TimestampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("closed", "Closed"),
    ]

    SENIORITY_CHOICES = [
        ("junior", "Junior"),
        ("mid", "Mid"),
        ("senior", "Senior"),
        ("staff", "Staff"),
        ("principal", "Principal"),
    ]

    EMPLOYMENT_CHOICES = [
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contract", "Contract"),
        ("internship", "Internship"),
    ]

    company = models.ForeignKey("accounts.Company", on_delete=models.CASCADE, related_name="jobs")
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="created_jobs")

    # Public apply flow
    public_slug = models.SlugField(max_length=120, unique=True, blank=True)

    # Core
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=120, blank=True)
    seniority = models.CharField(max_length=20, choices=SENIORITY_CHOICES, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_CHOICES, default="full_time")
    salary_range = models.CharField(max_length=120, blank=True)

    # Content
    summary = models.TextField(blank=True)
    responsibilities = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    nice_to_have = models.JSONField(default=list, blank=True)
    skills = models.JSONField(default=list, blank=True)

    # AI
    rubric = models.JSONField(default=list, blank=True)                  # [{criterion, weight, description}]
    screening_questions = models.JSONField(default=list, blank=True)     # [{text, why}]
    original_prompt = models.TextField(blank=True)
    ai_generated = models.BooleanField(default=False)

    # State
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.company.name})"

    def save(self, *args, **kwargs):
        if not self.public_slug:
            self.public_slug = self._generate_slug()
        super().save(*args, **kwargs)

    def _generate_slug(self) -> str:
        base = slugify(self.title) or "role"
        token = secrets.token_hex(3)
        return f"{base}-{token}"

    @property
    def counts(self) -> dict:
        candidates = self.applications.select_related("candidate")
        return {
            "applied": candidates.count(),
            "screening": candidates.filter(stage="screening").count(),
            "interview": candidates.filter(stage="interview").count(),
            "offer": candidates.filter(stage="offer").count(),
            "hired": candidates.filter(stage="hired").count(),
        }
