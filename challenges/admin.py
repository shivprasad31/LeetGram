from django.contrib import admin

from .models import Challenge, ChallengeEvent, ChallengeResult, ChallengeSubmission


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "challenger", "opponent", "status", "problem", "created_at", "start_time", "end_time")
    list_filter = ("status", "allowed_language", "created_at")
    search_fields = ("challenger__username", "opponent__username", "title_snapshot")


@admin.register(ChallengeSubmission)
class ChallengeSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "challenge", "user", "verdict", "is_correct", "execution_time", "submitted_at")
    list_filter = ("language", "verdict", "is_correct")
    search_fields = ("user__username", "challenge__title_snapshot")


@admin.register(ChallengeResult)
class ChallengeResultAdmin(admin.ModelAdmin):
    list_display = ("id", "challenge", "winner", "loser", "time_taken", "created_at")


@admin.register(ChallengeEvent)
class ChallengeEventAdmin(admin.ModelAdmin):
    list_display = ("id", "challenge", "user", "event_type", "timestamp")
    list_filter = ("event_type",)
