from django.contrib import admin

from .models import WeeklyReport


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ("company", "generated_by", "created_at")
    search_fields = ("company__name",)
