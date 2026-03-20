from django.conf import settings
from django.db import models


class ProfileStatistics(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_statistics")
    total_solved = models.PositiveIntegerField(default=0)
    easy_solved = models.PositiveIntegerField(default=0)
    medium_solved = models.PositiveIntegerField(default=0)
    hard_solved = models.PositiveIntegerField(default=0)
    contests_participated = models.PositiveIntegerField(default=0)
    contests_won = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-total_solved"]

    def __str__(self):
        return f"Stats for {self.user}"


class UserActivity(models.Model):
    activity_choices = [
        ("solve", "Solved Problem"),
        ("challenge", "Challenge"),
        ("contest", "Contest"),
        ("friend", "Friendship"),
        ("group", "Group"),
        ("revision", "Revision"),
        ("integration", "Integration"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=32, choices=activity_choices)
    description = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user} · {self.activity_type}"

