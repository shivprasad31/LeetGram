from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    category_choices = [
        ("friend", "Friend"),
        ("challenge", "Challenge"),
        ("contest", "Contest"),
        ("group", "Group"),
        ("revision", "Revision"),
        ("system", "System"),
    ]
    level_choices = [
        ("info", "Info"),
        ("success", "Success"),
        ("warning", "Warning"),
        ("danger", "Danger"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="triggered_notifications", blank=True, null=True)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=280)
    category = models.CharField(max_length=32, choices=category_choices, default="system")
    level = models.CharField(max_length=16, choices=level_choices, default="info")
    action_url = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]

    def mark_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])

    def __str__(self):
        return self.title

