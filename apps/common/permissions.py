from rest_framework.permissions import BasePermission


class HasCompanyMembership(BasePermission):
    """User must have an active membership in the company header `X-Company-Id`."""

    message = "You must be a member of this company."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        company = getattr(request, "company", None)
        return company is not None
