from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views


urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("magic-link/", views.request_magic_link, name="request-magic-link"),
    path("verify/", views.verify_magic_link, name="verify-magic-link"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.me, name="me"),
    path("me/update/", views.update_me, name="me-update"),
    path("me/avatar/", views.upload_avatar, name="me-avatar"),
    path("me/password/", views.change_password, name="me-password"),
    path("me/delete/", views.delete_account, name="me-delete"),
    path("me/sessions/", views.active_sessions, name="me-sessions"),
    path("me/sessions/revoke-all/", views.revoke_all_sessions, name="me-sessions-revoke"),
    path("company/", views.update_company, name="company-update"),
    path("company/logo/", views.upload_company_logo, name="company-logo"),
]
