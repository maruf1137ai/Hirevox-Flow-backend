from django.urls import path

from . import views


urlpatterns = [
    path("sessions/start/", views.start, name="session-start"),
    path("sessions/<str:token>/", views.session_detail, name="session-detail"),
    path("sessions/<str:token>/messages/", views.send_message, name="session-send-message"),
    path("sessions/<str:token>/voice/", views.voice_reply, name="session-voice-reply"),
]
