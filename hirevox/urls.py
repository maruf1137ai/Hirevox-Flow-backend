from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/jobs/", include("apps.jobs.urls")),
    path("api/v1/candidates/", include("apps.candidates.urls")),
    path("api/v1/screening/", include("apps.screening.urls")),
    path("api/v1/pipeline/", include("apps.pipeline.urls")),
    path("api/v1/insights/", include("apps.insights.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.common.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
