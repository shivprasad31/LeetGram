from django.conf import settings
from django.db import models


class DailyRanking(models.Model):
    date = models.DateField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_rankings")
    score = models.PositiveIntegerField(default=0)
    challenges_won = models.PositiveIntegerField(default=0)
    contest_points = models.PositiveIntegerField(default=0)
    solved_points = models.PositiveIntegerField(default=0)
    streak_bonus = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["date", "rank"]
        unique_together = ("date", "user")


class WeeklyRanking(models.Model):
    week_start = models.DateField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="weekly_rankings")
    score = models.PositiveIntegerField(default=0)
    challenges_won = models.PositiveIntegerField(default=0)
    contest_points = models.PositiveIntegerField(default=0)
    solved_points = models.PositiveIntegerField(default=0)
    streak_bonus = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["week_start", "rank"]
        unique_together = ("week_start", "user")


class GlobalLeaderboard(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="global_leaderboard")
    score = models.PositiveIntegerField(default=0)
    total_solved = models.PositiveIntegerField(default=0)
    challenges_won = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rank", "-score"]

    def __str__(self):
        return f"{self.user} · #{self.rank}"

