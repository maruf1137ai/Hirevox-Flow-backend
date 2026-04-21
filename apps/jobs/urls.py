from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views


router = DefaultRouter()
router.register(r"", views.JobViewSet, basename="job")


urlpatterns = [
    path("generate/", views.generate, name="job-generate"),
    path("public/", views.public_list, name="job-public-list"),
    path("public/<slug:slug>/", views.public_detail, name="job-public-detail"),
    path("", include(router.urls)),
]
