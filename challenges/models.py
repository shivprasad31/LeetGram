from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Challenge(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_ACTIVE = "active"
    STATUS_FINISHED = "finished"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FINISHED, "Finished"),
        (STATUS_REJECTED, "Rejected"),
    ]

    FINISH_REASON_COMPLETED = "completed"
    FINISH_REASON_DISQUALIFIED = "disqualified"
    FINISH_REASON_FORFEITED = "forfeited"
    FINISH_REASON_REJECTED = "rejected"

    FINISH_REASON_CHOICES = [
        (FINISH_REASON_COMPLETED, "Completed"),
        (FINISH_REASON_DISQUALIFIED, "Disqualified"),
        (FINISH_REASON_FORFEITED, "Forfeited"),
        (FINISH_REASON_REJECTED, "Rejected"),
    ]

    LANGUAGE_PYTHON = "python"
    LANGUAGE_JAVA = "java"
    LANGUAGE_CHOICES = [
        (LANGUAGE_PYTHON, "Python"),
        (LANGUAGE_JAVA, "Java"),
    ]

    challenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_challenges")
    opponent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_challenges")
    group = models.ForeignKey("groups.Group", on_delete=models.SET_NULL, related_name="battle_challenges", blank=True, null=True)
    problem = models.ForeignKey("problems.Problem", on_delete=models.SET_NULL, related_name="battle_challenges", blank=True, null=True)
    difficulty = models.ForeignKey("problems.ProblemDifficulty", on_delete=models.SET_NULL, related_name="challenges", blank=True, null=True)
    time_limit_minutes = models.PositiveIntegerField(default=90)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    allowed_language = models.CharField(max_length=16, choices=LANGUAGE_CHOICES, default=LANGUAGE_PYTHON)
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="won_challenges", blank=True, null=True)
    title_snapshot = models.CharField(max_length=255, blank=True)
    statement_snapshot = models.TextField(blank=True)
    constraints_snapshot = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    challenger_joined_at = models.DateTimeField(blank=True, null=True)
    opponent_joined_at = models.DateTimeField(blank=True, null=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    finish_reason = models.CharField(max_length=32, choices=FINISH_REASON_CHOICES, blank=True)
    disqualified_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="disqualified_challenges",
        blank=True,
        null=True,
    )
    challenger_camera_active = models.BooleanField(default=False)
    opponent_camera_active = models.BooleanField(default=False)
    challenger_camera_snapshot = models.TextField(blank=True)
    opponent_camera_snapshot = models.TextField(blank=True)
    challenger_camera_updated_at = models.DateTimeField(blank=True, null=True)
    opponent_camera_updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["challenger", "status"], name="challenges__challen_79d5a0_idx"),
            models.Index(fields=["opponent", "status"], name="challenges__opponen_783b17_idx"),
        ]

    def __str__(self):
        return f"{self.challenger} vs {self.opponent}"

    def clean(self):
        errors = {}
        if self.status == self.STATUS_PENDING and self.accepted_at:
            errors["accepted_at"] = "Pending challenges cannot have an acceptance time."
        if self.status == self.STATUS_PENDING and self.start_time:
            errors["start_time"] = "Pending challenges cannot have a start time."
        if self.status == self.STATUS_ACTIVE:
            if not self.accepted_at:
                errors["accepted_at"] = "Active challenges must be accepted first."
            if not self.challenger_joined_at or not self.opponent_joined_at:
                errors["status"] = "Both players must join before a challenge becomes active."
        if self.status == self.STATUS_FINISHED:
            if not self.end_time:
                errors["end_time"] = "Finished challenges must record an end time."
            if not self.winner_id and self.finish_reason != self.FINISH_REASON_REJECTED:
                errors["winner"] = "Finished challenges require a winner unless they were rejected."
        if self.status == self.STATUS_REJECTED and self.finish_reason not in {"", self.FINISH_REASON_REJECTED}:
            errors["finish_reason"] = "Rejected challenges must use the rejected finish reason."
        if errors:
            raise ValidationError(errors)

    @property
    def sender(self):
        return self.challenger

    @property
    def receiver(self):
        return self.opponent

    @property
    def is_ready_to_start(self):
        return bool(self.challenger_joined_at and self.opponent_joined_at)

    @property
    def can_view_problem(self):
        return self.status in {self.STATUS_ACTIVE, self.STATUS_FINISHED}


class ChallengeSubmission(models.Model):
    VERDICT_CORRECT = "correct"
    VERDICT_WRONG = "wrong"
    VERDICT_ERROR = "error"

    VERDICT_CHOICES = [
        (VERDICT_CORRECT, "Correct"),
        (VERDICT_WRONG, "Wrong"),
        (VERDICT_ERROR, "Error"),
    ]

    challenge = models.ForeignKey("challenges.Challenge", on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_submissions")
    code = models.TextField()
    language = models.CharField(max_length=16, choices=Challenge.LANGUAGE_CHOICES, default=Challenge.LANGUAGE_PYTHON)
    verdict = models.CharField(max_length=16, choices=VERDICT_CHOICES, default=VERDICT_ERROR)
    execution_time = models.FloatField(default=0.0)
    is_correct = models.BooleanField(default=False)
    time_taken_seconds = models.PositiveIntegerField(default=0)
    output = models.TextField(blank=True)
    error_output = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_at"]
        indexes = [
            models.Index(fields=["challenge", "user", "-submitted_at"], name="challenges__challen_5d3507_idx"),
        ]

    def __str__(self):
        return f"{self.user} in {self.challenge}"


class ChallengeResult(models.Model):
    challenge = models.OneToOneField("challenges.Challenge", on_delete=models.CASCADE, related_name="result")
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="won_battles", blank=True, null=True)
    loser = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="lost_battles", blank=True, null=True)
    winning_submission = models.ForeignKey(
        "challenges.ChallengeSubmission",
        on_delete=models.SET_NULL,
        related_name="winning_results",
        blank=True,
        null=True,
    )
    time_taken = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Result for {self.challenge}"


class ChallengeEvent(models.Model):
    EVENT_TAB_SWITCH = "tab_switch"
    EVENT_WINDOW_BLUR = "window_blur"
    EVENT_CAMERA_BLOCKED = "camera_blocked"
    EVENT_CAMERA_ENABLED = "camera_enabled"
    EVENT_CAMERA_HEARTBEAT = "camera_heartbeat"

    EVENT_CHOICES = [
        (EVENT_TAB_SWITCH, "Tab Switch"),
        (EVENT_WINDOW_BLUR, "Window Blur"),
        (EVENT_CAMERA_BLOCKED, "Camera Blocked"),
        (EVENT_CAMERA_ENABLED, "Camera Enabled"),
        (EVENT_CAMERA_HEARTBEAT, "Camera Heartbeat"),
    ]

    challenge = models.ForeignKey("challenges.Challenge", on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenge_events")
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["challenge", "user", "-timestamp"], name="challenges__challen_17754a_idx"),
        ]

    def __str__(self):
        return f"{self.user} · {self.event_type}"


class ChallengeProblem(models.Model):
    challenge = models.ForeignKey("challenges.Challenge", on_delete=models.CASCADE, related_name="challenge_problems")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="challenge_entries")
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["position"]
        unique_together = ("challenge", "problem")

    def __str__(self):
        return f"{self.challenge} · {self.problem}"
