from django.conf import settings
from django.db import models


class IntegrationStatus(models.Model):
    PLATFORM_CHOICES = [
        ("codeforces", "Codeforces"),
        ("leetcode", "LeetCode"),
        ("gfg", "GeeksForGeeks"),
        ("hackerrank", "HackerRank"),
    ]

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="integration_statuses")
    platform = models.CharField(max_length=32, choices=PLATFORM_CHOICES)
    last_synced = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="success")
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["user_id", "platform"]
        unique_together = ("user", "platform")
        indexes = [
            models.Index(fields=["platform", "last_synced"]),
            models.Index(fields=["user", "platform"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.platform}"