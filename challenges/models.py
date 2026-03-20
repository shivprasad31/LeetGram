from django.conf import settings
from django.db import models


class Challenge(models.Model):
    status_choices = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("running", "Running"),
        ("finished", "Finished"),
        ("declined", "Declined"),
        ("expired", "Expired"),
    ]

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_challenges")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_challenges")
    difficulty = models.ForeignKey("problems.ProblemDifficulty", on_delete=models.SET_NULL, related_name="challenges", blank=True, null=True)
    time_limit_minutes = models.PositiveIntegerField(default=90)
    status = models.CharField(max_length=16, choices=status_choices, default="pending")
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="won_challenges", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return f"{self.sender} vs {self.receiver}"


class ChallengeProblem(models.Model):
    challenge = models.ForeignKey("challenges.Challenge", on_delete=models.CASCADE, related_name="challenge_problems")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="challenge_entries")
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["position"]
        unique_together = ("challenge", "problem")

    def __str__(self):
        return f"{self.challenge} · {self.problem}"


class ChallengeResult(models.Model):
    challenge = models.ForeignKey("challenges.Challenge", on_delete=models.CASCADE, related_name="results")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_results")
    score = models.PositiveIntegerField(default=0)
    solved_count = models.PositiveSmallIntegerField(default=0)
    completion_time_seconds = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("challenge", "user")
        ordering = ["score", "completion_time_seconds"]

    def __str__(self):
        return f"{self.user} in {self.challenge}"

