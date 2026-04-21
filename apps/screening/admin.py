from django.contrib import admin

from .models import InterviewMessage, InterviewSession


class InterviewMessageInline(admin.TabularInline):
    model = InterviewMessage
    extra = 0
    readonly_fields = ("role", "body", "created_at")


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ("application", "status", "turns_count", "started_at", "completed_at")
    list_filter = ("status",)
    inlines = [InterviewMessageInline]
    readonly_fields = ("started_at", "completed_at", "turns_count", "created_at", "updated_at")
