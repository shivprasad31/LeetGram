from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Contest(models.Model):
    visibility_choices = [
        ("public", "Public"),
        ("private", "Private"),
        ("group", "Group"),
    ]
    status_choices = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("live", "Live"),
        ("finished", "Finished"),
    ]

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_contests")
    group = models.ForeignKey("groups.Group", on_delete=models.SET_NULL, related_name="contests", blank=True, null=True)
    start_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=120)
    difficulty = models.ForeignKey("problems.ProblemDifficulty", on_delete=models.SET_NULL, related_name="contests", blank=True, null=True)
    visibility = models.CharField(max_length=16, choices=visibility_choices, default="public")
    status = models.CharField(max_length=16, choices=status_choices, default="draft")
    is_team_based = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 2
            while Contest.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ContestProblem(models.Model):
    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="contest_problems")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="contest_entries")
    order = models.PositiveSmallIntegerField(default=1)
    points = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["order"]
        unique_together = ("contest", "problem")

    def __str__(self):
        return f"{self.contest} · {self.problem}"


class ContestTeam(models.Model):
    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="teams")
    group = models.ForeignKey("groups.Group", on_delete=models.SET_NULL, related_name="contest_teams", blank=True, null=True)
    name = models.CharField(max_length=120)
    captain = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="captained_teams")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("contest", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ContestParticipant(models.Model):
    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contest_participations")
    team = models.ForeignKey("contests.ContestTeam", on_delete=models.SET_NULL, related_name="participants", blank=True, null=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    final_score = models.PositiveIntegerField(default=0)
    penalty = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("contest", "user")
        ordering = ["rank", "-final_score"]

    def __str__(self):
        return f"{self.user} in {self.contest}"


class ContestSubmission(models.Model):
    verdict_choices = [
        ("accepted", "Accepted"),
        ("wrong_answer", "Wrong Answer"),
        ("time_limit", "Time Limit"),
        ("runtime_error", "Runtime Error"),
        ("partial", "Partial"),
    ]

    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="submissions")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="contest_submissions")
    participant = models.ForeignKey("contests.ContestParticipant", on_delete=models.CASCADE, related_name="submissions", blank=True, null=True)
    team = models.ForeignKey("contests.ContestTeam", on_delete=models.CASCADE, related_name="submissions", blank=True, null=True)
    language = models.CharField(max_length=32, default="python")
    code_snippet = models.TextField(blank=True)
    verdict = models.CharField(max_length=16, choices=verdict_choices, default="wrong_answer")
    score = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_at"]
        indexes = [models.Index(fields=["contest", "problem", "submitted_at"])]

    def __str__(self):
        return f"Submission {self.pk}"


class ContestLeaderboard(models.Model):
    contest = models.ForeignKey("contests.Contest", on_delete=models.CASCADE, related_name="leaderboard_entries")
    participant = models.ForeignKey("contests.ContestParticipant", on_delete=models.CASCADE, related_name="leaderboard_entries", blank=True, null=True)
    team = models.ForeignKey("contests.ContestTeam", on_delete=models.CASCADE, related_name="leaderboard_entries", blank=True, null=True)
    score = models.PositiveIntegerField(default=0)
    penalty = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)
    last_submission_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["rank", "-score", "penalty"]
        constraints = [
            models.UniqueConstraint(fields=["contest", "participant"], condition=models.Q(participant__isnull=False), name="unique_contest_participant_board"),
            models.UniqueConstraint(fields=["contest", "team"], condition=models.Q(team__isnull=False), name="unique_contest_team_board"),
        ]

    def __str__(self):
        return f"Leaderboard {self.contest} #{self.rank}"

