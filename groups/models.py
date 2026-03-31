from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


class Group(models.Model):
    privacy_choices = [
        ("public", "Public"),
        ("private", "Private"),
        ("invite_only", "Invite Only"),
    ]

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="group_avatars/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="group_covers/", blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_groups")
    privacy = models.CharField(max_length=16, choices=privacy_choices, default="invite_only")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="GroupMembership", related_name="study_groups")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 2
            while Group.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def created_by(self):
        return self.owner

    @property
    def member_count(self):
        return self.memberships.count()

    def is_admin(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.memberships.filter(user=user, role__in=["owner", "admin"]).exists()

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    role_choices = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=16, choices=role_choices, default="member")
    joined_at = models.DateTimeField(auto_now_add=True)
    is_muted = models.BooleanField(default=False)
    total_challenges = models.PositiveIntegerField(default=0)
    challenge_wins = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("group", "user")
        ordering = ["group", "-joined_at"]

    def __str__(self):
        return f"{self.user} in {self.group}"


class GroupInvite(models.Model):
    status_choices = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("cancelled", "Cancelled"),
    ]

    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="invites")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_group_invites")
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_invites")
    status = models.CharField(max_length=16, choices=status_choices, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["group", "invitee"], condition=Q(status="pending"), name="unique_pending_group_invite"),
        ]

    def clean(self):
        if self.invited_by_id == self.invitee_id:
            raise ValidationError("You cannot invite yourself to a group.")
        if self.group_id and self.invitee_id and GroupMembership.objects.filter(group_id=self.group_id, user_id=self.invitee_id).exists():
            raise ValidationError("This user is already a member of the group.")

    def mark(self, status):
        self.status = status
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def accept(self):
        GroupMembership.objects.get_or_create(group=self.group, user=self.invitee, defaults={"role": "member"})
        self.mark("accepted")

    def reject(self):
        self.mark("declined")

    @property
    def from_user(self):
        return self.invited_by

    @property
    def to_user(self):
        return self.invitee

    def __str__(self):
        return f"Invite {self.invitee} to {self.group}"


class GroupTask(models.Model):
    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="tasks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_group_tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=32, blank=True)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.group}: {self.title}"


class GroupTaskCompletion(models.Model):
    task = models.ForeignKey("groups.GroupTask", on_delete=models.CASCADE, related_name="completions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="completed_group_tasks")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        unique_together = ("task", "user")
        indexes = [models.Index(fields=["task", "user"])]

    def __str__(self):
        return f"{self.user} completed {self.task}"


class GroupChallenge(models.Model):
    status_choices = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]

    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE, related_name="group_challenges")
    challenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_challenges_started")
    opponent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_challenges_received")
    problem = models.ForeignKey("problems.Problem", on_delete=models.SET_NULL, related_name="group_challenges", blank=True, null=True)
    status = models.CharField(max_length=16, choices=status_choices, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(challenger=models.F("opponent")), name="group_challenge_not_self"),
        ]
        indexes = [models.Index(fields=["group", "status", "-created_at"])]

    def __str__(self):
        return f"{self.challenger} vs {self.opponent} in {self.group}"
