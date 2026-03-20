from django.conf import settings
from django.db import models
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
    privacy = models.CharField(max_length=16, choices=privacy_choices, default="public")
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
            models.UniqueConstraint(fields=["group", "invitee"], condition=models.Q(status="pending"), name="unique_pending_group_invite"),
        ]

    def __str__(self):
        return f"Invite {self.invitee} to {self.group}"

