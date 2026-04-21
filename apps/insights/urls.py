from django.urls import path

from . import views


urlpatterns = [
    path("overview/", views.overview, name="insights-overview"),
    path("", views.insights, name="insights-detail"),
    path("generate/", views.generate, name="insights-generate"),
]
