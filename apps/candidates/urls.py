from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register(r"", views.ApplicationViewSet, basename="application")


urlpatterns = [
    path("public/progress/<str:token>/", views.application_progress, name="application-progress"),
    path("public/reply/<str:token>/", views.candidate_reply, name="application-reply"),
    path("public/<slug:slug>/apply/", views.public_apply, name="application-public-apply"),
    path("my-applications/", views.my_applications, name="candidate-my-applications"),
    path("export/", views.export_csv, name="application-export"),
    path("", include(router.urls)),
]
