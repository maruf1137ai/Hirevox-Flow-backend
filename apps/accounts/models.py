import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.common.models import TimestampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)
    title = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def initials(self) -> str:
        if not self.name:
            return self.email[:2].upper()
        parts = self.name.split()
        return "".join(p[0] for p in parts[:2]).upper()


class Company(TimestampedModel):
    SIZE_CHOICES = [
        ("1-10", "1–10"),
        ("11-50", "11–50"),
        ("51-200", "51–200"),
        ("200+", "200+"),
    ]

    TONE_CHOICES = [
        ("professional", "Professional"),
        ("warm", "Warm"),
        ("direct", "Direct"),
        ("playful", "Playful"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    website = models.URLField(blank=True)
    size = models.CharField(max_length=20, choices=SIZE_CHOICES, default="1-10")
    logo_url = models.URLField(blank=True)
    accent_color = models.CharField(max_length=7, default="#4F46E5")
    tone = models.CharField(max_length=20, choices=TONE_CHOICES, default="professional")

    # AI preferences
    auto_rank = models.BooleanField(default=True)
    auto_advance = models.BooleanField(default=False)
    voice_interviews = models.BooleanField(default=True)
    pii_redaction = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class Membership(TimestampedModel):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "company")
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.user.email} @ {self.company.name} ({self.role})"

class MagicLinkToken(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="magic_tokens")
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def __str__(self):
        return f"Magic link for {self.user.email}"
