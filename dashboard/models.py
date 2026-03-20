from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    theme_choices = [
        ("light", "Light"),
        ("dark", "Dark"),
        ("system", "System"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference")
    theme_mode = models.CharField(max_length=16, choices=theme_choices, default="light")
    accent_color = models.CharField(max_length=7, default="#FF6B6B")
    reduce_motion = models.BooleanField(default=False)
    dashboard_layout = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user}"

