import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def default_token_expiry():
    return timezone.now() + timezone.timedelta(days=2)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    rating = models.PositiveIntegerField(default=1200, db_index=True)
    rank = models.CharField(max_length=64, blank=True)
    streak = models.PositiveIntegerField(default=0)
    solved_count = models.PositiveIntegerField(default=0, db_index=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    github = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["-rating", "username"]
        indexes = [
            models.Index(fields=["rating"]),
            models.Index(fields=["solved_count"]),
            models.Index(fields=["streak"]),
        ]

    def __str__(self):
        return self.username or self.email




class Badge(models.Model):
    category_choices = [
        ("solving", "Solving"),
        ("contests", "Contests"),
        ("social", "Social"),
        ("revision", "Revision"),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=category_choices)
    icon = models.CharField(max_length=64, default="bi-award")
    threshold = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["category", "threshold", "name"]

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey("users.Badge", on_delete=models.CASCADE, related_name="holders")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")
        ordering = ["-awarded_at"]

    def __str__(self):
        return f"{self.user} · {self.badge}"

