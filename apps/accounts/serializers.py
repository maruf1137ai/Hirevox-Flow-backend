from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Company, Membership, User


class UserSerializer(serializers.ModelSerializer):
    initials = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "name", "title", "avatar_url", "initials", "created_at")
        read_only_fields = ("id", "created_at")

    def get_avatar_url(self, obj):
        url = obj.avatar_url or ""
        if url and url.startswith("/"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(url)
        return url


class CompanySerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id", "name", "slug", "website", "size", "logo_url",
            "accent_color", "tone",
            "auto_rank", "auto_advance", "voice_interviews", "pii_redaction",
            "created_at",
        )
        read_only_fields = ("id", "slug", "created_at")

    def get_logo_url(self, obj):
        url = obj.logo_url or ""
        if url and url.startswith("/"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(url)
        return url


class MembershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "company", "role", "is_active", "created_at")


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    company = serializers.CharField(max_length=200)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        user = User.objects.create_user(
            email=email,
            password=validated_data["password"],
            name=validated_data["name"],
        )

        base_slug = slugify(validated_data["company"]) or "company"
        slug = base_slug
        n = 1
        while Company.objects.filter(slug=slug).exists():
            n += 1
            slug = f"{base_slug}-{n}"

        company = Company.objects.create(name=validated_data["company"], slug=slug)
        Membership.objects.create(user=user, company=company, role="owner")
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MeSerializer(serializers.Serializer):
    user = UserSerializer()
    active_company = CompanySerializer(allow_null=True)
    memberships = MembershipSerializer(many=True)


def tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
