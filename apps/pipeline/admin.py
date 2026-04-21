from django.contrib import admin

from .models import StageTransition


@admin.register(StageTransition)
class StageTransitionAdmin(admin.ModelAdmin):
    list_display = ("application", "from_stage", "to_stage", "moved_by", "created_at")
    list_filter = ("from_stage", "to_stage")
