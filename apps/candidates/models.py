import secrets
from django.db import models

from apps.common.models import TimestampedModel


class Candidate(TimestampedModel):
    """A person. Belongs to a company (scoped); unique on email-per-company."""

    company = models.ForeignKey("accounts.Company", on_delete=models.CASCADE, related_name="candidates")

    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=200, blank=True)

    current_role = models.CharField(max_length=200, blank=True)
    current_company = models.CharField(max_length=200, blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)

    resume = models.FileField(upload_to="resumes/", blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)

    # Scraped from GitHub, Portfolio, etc.
    # Shape: {"github": {...}, "portfolio": {...}, "overall_summary": "...", "tech_stack": [...]}
    external_intelligence = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("company", "email")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def initials(self) -> str:
        parts = self.name.split()
        return "".join(p[0] for p in parts[:2]).upper() if parts else "?"


class Application(TimestampedModel):
    """A candidate's application to a specific job."""

    STAGE_CHOICES = [
        ("applied", "Applied"),
        ("screening", "Screening"),
        ("interview", "Interview"),
        ("offer", "Offer"),
        ("hired", "Hired"),
        ("rejected", "Rejected"),
    ]

    STATUS_CHOICES = [
        ("recommended", "Recommended"),
        ("shortlist", "Shortlist"),
        ("review", "Review"),
        ("rejected", "Rejected"),
    ]

    SOURCE_CHOICES = [
        ("direct", "Direct apply"),
        ("referral", "Referral"),
        ("linkedin", "LinkedIn"),
        ("indeed", "Indeed"),
        ("network", "Hirevox Network"),
        ("other", "Other"),
    ]

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="applications")
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="applications")
    # Denormalised for fast scoping; also lets us preserve the reference if candidate is deleted later.
    company = models.ForeignKey("accounts.Company", on_delete=models.CASCADE, related_name="applications")

    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="applied")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="review")
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="direct")

    # Scoring (populated once interview completes)
    score = models.IntegerField(null=True, blank=True)
    ai_summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    considerations = models.JSONField(default=list, blank=True)
    rubric_scores = models.JSONField(default=list, blank=True)  # [{criterion, score, evidence, reasoning}]

    # Recruiter-facing cheat sheet. Generated on demand from rubric gaps.
    # Shape: {"focus_areas": [...], "summary": "...", "questions": [{question, focus, rationale, tip}, ...], "generated_at": iso}
    interview_cheatsheet = models.JSONField(default=dict, blank=True)

    # Access token for the candidate to resume their interview (single-use-ish).
    access_token = models.CharField(max_length=64, unique=True, blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_stage = self.stage

    @property
    def tracker_enabled(self) -> bool:
        """Helper for notification triggers. Can be extended to per-company settings later."""
        return True

    class Meta:
        unique_together = ("candidate", "job")
        ordering = ("-score", "-created_at")
        indexes = [
            models.Index(fields=["company", "stage"]),
            models.Index(fields=["job", "stage"]),
        ]

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.candidate.name} → {self.job.title}"


class Note(TimestampedModel):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="notes")
    body = models.TextField()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Note by {self.author} on {self.application}"


class Message(TimestampedModel):
    """A communication entry between a recruiter and a candidate."""

    SENDER_CHOICES = [
        ("recruiter", "Recruiter"),
        ("candidate", "Candidate"),
    ]
    TYPE_CHOICES = [
        ("email", "Email"),
        ("chat", "Chat"),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="messages")
    sender_type = models.CharField(max_length=20, choices=SENDER_CHOICES)
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="chat")

    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()

    is_read = models.BooleanField(default=False)
    # If sent by a recruiter, link to them
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.message_type} from {self.sender_type} for {self.application.candidate.name}"
