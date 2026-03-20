from django.conf import settings
from django.db import models


class ExternalProfileConnection(models.Model):
    platform_choices = [
        ("leetcode", "LeetCode"),
        ("codeforces", "Codeforces"),
        ("gfg", "GeeksForGeeks"),
    ]
    sync_status_choices = [
        ("idle", "Idle"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="external_profiles")
    platform = models.CharField(max_length=16, choices=platform_choices)
    username = models.CharField(max_length=120)
    profile_url = models.URLField(blank=True)
    api_token = models.CharField(max_length=255, blank=True)
    session_cookie = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    sync_status = models.CharField(max_length=16, choices=sync_status_choices, default="idle")
    remote_rating = models.IntegerField(default=0)
    remote_solved_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["platform", "username"]
        unique_together = ("user", "platform")

    def __str__(self):
        return f"{self.user} on {self.platform}"

