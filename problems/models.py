from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class ProblemDifficulty(models.Model):
    name = models.CharField(max_length=32, unique=True)
    slug = models.SlugField(max_length=32, unique=True, blank=True)
    weight = models.PositiveIntegerField(default=1)
    color = models.CharField(max_length=7, default="#4ECDC4")

    class Meta:
        ordering = ["weight", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProblemTag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True, blank=True)
    color = models.CharField(max_length=7, default="#FF6B6B")

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Problem(models.Model):
    platform_choices = [
        ("leetcode", "LeetCode"),
        ("codeforces", "Codeforces"),
        ("gfg", "GeeksForGeeks"),
        ("custom", "Custom"),
    ]

    external_id = models.CharField(max_length=128, blank=True, null=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    statement = models.TextField(blank=True)
    url = models.URLField(blank=True)
    platform = models.CharField(max_length=16, choices=platform_choices, default="custom")
    source = models.CharField(max_length=120, blank=True)
    difficulty = models.ForeignKey("problems.ProblemDifficulty", on_delete=models.PROTECT, related_name="problems")
    tags = models.ManyToManyField("problems.ProblemTag", related_name="problems", blank=True)
    acceptance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    points = models.PositiveIntegerField(default=100)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "external_id"], condition=models.Q(external_id__isnull=False), name="unique_problem_per_platform")
        ]
        indexes = [
            models.Index(fields=["platform", "difficulty"]),
            models.Index(fields=["title"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 2
            while Problem.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class UserSolvedProblem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solved_problems")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="solvers")
    platform = models.CharField(max_length=16, blank=True)
    submission_id = models.CharField(max_length=120, blank=True)
    solved_at = models.DateTimeField(default=timezone.now)
    runtime_ms = models.PositiveIntegerField(blank=True, null=True)
    memory_kb = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)
    source_rating_change = models.IntegerField(default=0)

    class Meta:
        ordering = ["-solved_at"]
        constraints = [models.UniqueConstraint(fields=["user", "problem"], name="unique_solved_problem_per_user")]
        indexes = [
            models.Index(fields=["user", "-solved_at"]),
            models.Index(fields=["problem"]),
        ]

    def __str__(self):
        return f"{self.user} solved {self.problem}"

