class CompanyScopedMixin:
    """ViewSet mixin that filters queryset by `request.company`."""

    company_field = "company"

    def get_queryset(self):
        qs = super().get_queryset()
        company = getattr(self.request, "company", None)
        if company is None:
            return qs.none()
        return qs.filter(**{self.company_field: company})

    def perform_create(self, serializer):
        serializer.save(**{self.company_field: self.request.company})
