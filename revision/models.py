from django.conf import settings
from django.db import models
from django.utils import timezone


class RevisionList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="revision_lists")
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "title"]

    def __str__(self):
        return self.title


class RevisionItem(models.Model):
    revision_list = models.ForeignKey("revision.RevisionList", on_delete=models.CASCADE, related_name="items")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="revision_items")
    next_review_at = models.DateTimeField(default=timezone.now)
    last_reviewed_at = models.DateTimeField(blank=True, null=True)
    interval_days = models.PositiveIntegerField(default=1)
    ease_factor = models.DecimalField(max_digits=3, decimal_places=2, default=2.50)
    repetitions = models.PositiveIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(default=3)
    is_mastered = models.BooleanField(default=False)

    class Meta:
        unique_together = ("revision_list", "problem")
        ordering = ["next_review_at"]

    def __str__(self):
        return f"{self.problem} in {self.revision_list}"


class RevisionNotes(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="revision_notes")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="revision_notes")
    notes = models.TextField(blank=True)
    memory_hook = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "problem")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Notes for {self.problem}"



