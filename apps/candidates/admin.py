from django.contrib import admin

from .models import Application, Candidate, Note


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company", "current_company", "created_at")
    search_fields = ("name", "email", "current_company")
    list_filter = ("company",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "stage", "status", "score", "created_at")
    list_filter = ("stage", "status", "source")
    search_fields = ("candidate__name", "candidate__email", "job__title")
    readonly_fields = ("access_token", "created_at", "updated_at")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("application", "author", "created_at")
