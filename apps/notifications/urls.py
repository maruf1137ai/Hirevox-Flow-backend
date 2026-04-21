from django.urls import path
from . import views

urlpatterns = [
    path("", views.list_notifications, name="notifications-list"),
    path("unread/", views.unread_count, name="notifications-unread"),
    path("read-all/", views.mark_all_read, name="notifications-read-all"),
    path("<uuid:pk>/read/", views.mark_read, name="notification-read"),
    path("<uuid:pk>/", views.delete_notification, name="notification-delete"),
]
