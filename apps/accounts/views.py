import os
import uuid
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

import secrets
from django.utils import timezone
from .models import Company, MagicLinkToken, Membership, User
from .serializers import (
    CompanySerializer,
    LoginSerializer,
    MembershipSerializer,
    SignupSerializer,
    UserSerializer,
    tokens_for_user,
)


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    membership = user.memberships.select_related("company").first()
    ctx = {"request": request}
    return Response({
        "user": UserSerializer(user, context=ctx).data,
        "active_company": CompanySerializer(membership.company, context=ctx).data if membership else None,
        "tokens": tokens_for_user(user),
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"].lower()
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)
    if not user:
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    membership = user.memberships.filter(is_active=True).select_related("company").first()
    ctx = {"request": request}
    return Response({
        "user": UserSerializer(user, context=ctx).data,
        "active_company": CompanySerializer(membership.company, context=ctx).data if membership else None,
        "tokens": tokens_for_user(user),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    memberships = list(request.user.memberships.filter(is_active=True).select_related("company"))
    active = getattr(request, "company", None)
    if not active and memberships:
        active = memberships[0].company
    ctx = {"request": request}
    return Response({
        "user": UserSerializer(request.user, context=ctx).data,
        "active_company": CompanySerializer(active, context=ctx).data if active else None,
        "memberships": MembershipSerializer(memberships, many=True, context=ctx).data,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_me(request):
    serializer = UserSerializer(request.user, data=request.data, partial=True, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_avatar(request):
    """Upload user avatar image."""
    file = request.FILES.get("avatar")
    if not file:
        return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
    if file.size > 5 * 1024 * 1024:
        return Response({"detail": "File too large (max 5MB)."}, status=status.HTTP_400_BAD_REQUEST)

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return Response({"detail": "Invalid file type."}, status=status.HTTP_400_BAD_REQUEST)

    from django.core.files.storage import default_storage
    from django.conf import settings as django_settings

    filename = f"avatars/user_{request.user.id}{ext}"
    default_storage.delete(filename)
    default_storage.save(filename, file)
    relative = f"{django_settings.MEDIA_URL}{filename}"
    url = request.build_absolute_uri(relative)
    request.user.avatar_url = url
    request.user.save(update_fields=["avatar_url"])
    return Response({"avatar_url": url})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_company_logo(request):
    """Upload company logo image."""
    company = getattr(request, "company", None)
    if company is None:
        return Response({"detail": "No active company."}, status=status.HTTP_400_BAD_REQUEST)

    file = request.FILES.get("logo")
    if not file:
        return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
    if file.size > 5 * 1024 * 1024:
        return Response({"detail": "File too large (max 5MB)."}, status=status.HTTP_400_BAD_REQUEST)

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
        return Response({"detail": "Invalid file type."}, status=status.HTTP_400_BAD_REQUEST)

    from django.core.files.storage import default_storage
    from django.conf import settings as django_settings

    filename = f"logos/company_{company.id}{ext}"
    default_storage.delete(filename)
    default_storage.save(filename, file)
    relative = f"{django_settings.MEDIA_URL}{filename}"
    url = request.build_absolute_uri(relative)
    company.logo_url = url
    company.save(update_fields=["logo_url"])
    return Response({"logo_url": url})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    old = request.data.get("old_password", "")
    new = request.data.get("new_password", "")

    if not request.user.check_password(old):
        return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_password(new, request.user)
    except ValidationError as e:
        return Response({"detail": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(new)
    request.user.save(update_fields=["password"])
    return Response({"detail": "Password updated successfully."})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_account(request):
    password = request.data.get("password", "")
    if not request.user.check_password(password):
        return Response({"detail": "Password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
    request.user.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_sessions(request):
    """Return outstanding (non-blacklisted) refresh tokens for the user."""
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
    from django.utils import timezone

    tokens = OutstandingToken.objects.filter(
        user=request.user,
        expires_at__gt=timezone.now(),
    ).exclude(blacklisted__isnull=False).order_by("-created_at")[:10]

    return Response([
        {
            "id": str(t.id),
            "jti": t.jti,
            "created_at": t.created_at.isoformat(),
            "expires_at": t.expires_at.isoformat(),
        }
        for t in tokens
    ])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_all_sessions(request):
    """Blacklist all outstanding refresh tokens for the user (force logout everywhere)."""
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
    from django.utils import timezone

    tokens = OutstandingToken.objects.filter(
        user=request.user,
        expires_at__gt=timezone.now(),
    )
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)
    return Response({"detail": f"Revoked {tokens.count()} session(s)."})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_company(request):
    company = getattr(request, "company", None)
    if company is None:
        return Response(
            {"detail": "No active company."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    membership = request.membership
    if membership.role not in ("owner", "admin"):
        return Response(
            {"detail": "Only owners and admins can edit the company."},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = CompanySerializer(company, data=request.data, partial=True, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([AllowAny])
def request_magic_link(request):
    """Generate and 'send' a magic link for a user's email."""
    email = (request.data or {}).get("email", "").lower().strip()
    if not email:
        return Response({"detail": "Email is required."}, status=400)

    user, created = User.objects.get_or_create(email=email)
    
    # Invalidate old tokens
    MagicLinkToken.objects.filter(user=user, is_used=False).update(is_used=True)
    
    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timezone.timedelta(minutes=15)
    
    MagicLinkToken.objects.create(
        user=user,
        token=token,
        expires_at=expires_at
    )
    
    # In a real app, send actual email. For now, it will print to console as per settings.
    magic_url = f"{settings.WEBSITE_URL}/auth/verify?token={token}"
    print(f"\n[MAGIC LINK] for {email}: {magic_url}\n")
    
    return Response({"detail": "Magic link sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_magic_link(request):
    """Verify a magic link token and return auth tokens."""
    token = (request.data or {}).get("token", "")
    if not token:
        return Response({"detail": "Token is required."}, status=400)

    try:
        magic_token = MagicLinkToken.objects.get(token=token)
    except MagicLinkToken.DoesNotExist:
        return Response({"detail": "Invalid or expired token."}, status=400)

    if not magic_token.is_valid():
        return Response({"detail": "Invalid or expired token."}, status=400)

    magic_token.is_used = True
    magic_token.save()

    user = magic_token.user
    
    return Response({
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name or user.email.split("@")[0],
            "initials": user.initials,
        },
        "tokens": tokens_for_user(user),
    })
