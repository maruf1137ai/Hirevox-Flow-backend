from django.urls import path
from .views import health, ping, search


urlpatterns = [
    path("health/", health, name="health"),
    path("ping/", ping, name="ping"),
    path("search/", search, name="search"),
]
