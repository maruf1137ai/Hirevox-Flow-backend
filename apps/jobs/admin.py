from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "status", "ai_generated", "published_at", "created_at")
    list_filter = ("status", "ai_generated", "employment_type")
    search_fields = ("title", "company__name")
    readonly_fields = ("public_slug", "created_at", "updated_at")
