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


class Tag(models.Model):
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
    """
    Canonical problem entity.
    """
    canonical_name = models.CharField(max_length=255, default="")
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    difficulty = models.ForeignKey("problems.ProblemDifficulty", on_delete=models.PROTECT, related_name="problems", null=True)
    statement = models.TextField(blank=True)
    constraints = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=100)
    tags = models.ManyToManyField("problems.Tag", related_name="problems", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.canonical_name)
            slug = base_slug
            counter = 2
            while Problem.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.canonical_name

    @property
    def title(self):
        return self.canonical_name

    @property
    def description(self):
        return self.statement


class TestCase(models.Model):
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="test_cases")
    input_data = models.TextField()
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_sample", "id"]

    def __str__(self):
        return f"TestCase #{self.pk} for {self.problem}"


class PlatformProblem(models.Model):
    PLATFORM_CHOICES = [
        ("leetcode", "LeetCode"),
        ("codeforces", "Codeforces"),
        ("gfg", "GeeksForGeeks"),
        ("hackerrank", "HackerRank"),
        ("custom", "Custom"),
    ]

    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES, default="leetcode")
    platform_id = models.CharField(max_length=128, default="")
    title = models.CharField(max_length=255, default="")
    url = models.URLField(blank=True)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="platform_problems", null=True)

    class Meta:
        unique_together = ("platform", "platform_id")
        indexes = [
            models.Index(fields=["platform", "platform_id"]),
        ]

    def __str__(self):
        return f"[{self.platform}] {self.title}"


class UserSolvedProblem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="solved_problems")
    platform_problem = models.ForeignKey(PlatformProblem, on_delete=models.CASCADE, related_name="solvers", null=True)
    solved_at = models.DateTimeField(default=timezone.now)
    language = models.CharField(max_length=32, blank=True)
    runtime_ms = models.PositiveIntegerField(blank=True, null=True)
    memory_kb = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-solved_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "platform_problem"], name="unique_solved_problem_per_user")
        ]
        indexes = [
            models.Index(fields=["user", "-solved_at"]),
        ]

    def __str__(self):
        return f"{self.user} solved {self.platform_problem}"


