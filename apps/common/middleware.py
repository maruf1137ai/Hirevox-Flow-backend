"""Resolve the active company for the request from `X-Company-Id` header.

Falls back to the user's first active membership. Attaches `request.company`
and `request.membership` for downstream views / permissions.
"""

from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication


class ActiveCompanyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.company = None
        request.membership = None

        # Authenticate via JWT (independent of DRF's later auth pass so the
        # middleware resolving company works uniformly for DRF + admin).
        auth = JWTAuthentication()
        try:
            result = auth.authenticate(request)
        except Exception:
            result = None

        if result is None:
            return

        user, _ = result
        from apps.accounts.models import Membership

        company_id = request.headers.get("X-Company-Id")
        qs = Membership.objects.filter(user=user, is_active=True).select_related("company")
        if company_id:
            membership = qs.filter(company_id=company_id).first()
            # If the header points to an unknown/inaccessible company, fall back
            # to the user's first membership rather than leaving company as None.
            if membership is None:
                membership = qs.order_by("created_at").first()
        else:
            membership = qs.order_by("created_at").first()

        if membership:
            request.company = membership.company
            request.membership = membership
        request.user_from_jwt = user
