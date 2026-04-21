from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.candidates.models import Application

from . import services
from .models import InterviewSession
from .serializers import (
    InterviewSessionSerializer,
    SendMessageSerializer,
    StartSessionSerializer,
)


def _get_application_by_token(token: str) -> Application:
    return get_object_or_404(Application, access_token=token)


@api_view(["POST"])
@permission_classes([AllowAny])
def start(request):
    """Candidate opens their interview link. Creates session + emits first AI greeting."""
    serializer = StartSessionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    app = _get_application_by_token(serializer.validated_data["access_token"])
    session = services.start_session(app)
    return Response(InterviewSessionSerializer(session).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def session_detail(request, token):
    app = _get_application_by_token(token)
    session = get_object_or_404(InterviewSession, application=app)
    return Response(InterviewSessionSerializer(session).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def send_message(request, token):
    """Candidate sends a turn. Server replies with AI follow-up."""
    app = _get_application_by_token(token)
    session = get_object_or_404(InterviewSession, application=app)
    if session.status == "completed":
        return Response({"detail": "Interview already complete."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = services.reply(session, serializer.validated_data["body"])
    return Response({
        "session": InterviewSessionSerializer(session).data,
        **result,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def voice_reply(request, token):
    """Candidate sends audio blob. Server transcribes, logic-checks, and speaks back."""
    app = _get_application_by_token(token)
    session = get_object_or_404(InterviewSession, application=app)

    if session.status == "completed":
        return Response({"detail": "Interview already complete."}, status=status.HTTP_400_BAD_REQUEST)

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return Response({"detail": "Audio file is required."}, status=400)

    # Process audio through transcription -> brain -> synthesis
    result = services.voice_reply(session, audio_file)

    return Response({
        "session": InterviewSessionSerializer(session).data,
        **result,
    })
