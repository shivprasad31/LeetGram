from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class FriendRequest(models.Model):
    status_choices = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("cancelled", "Cancelled"),
    ]

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_friend_requests")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_friend_requests")
    message = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=16, choices=status_choices, default="pending")
    responded_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(sender=models.F("receiver")), name="friend_request_not_to_self"),
            models.UniqueConstraint(fields=["sender", "receiver"], condition=Q(status="pending"), name="unique_pending_friend_request"),
        ]

    def clean(self):
        if self.sender_id == self.receiver_id:
            raise ValidationError("You cannot send a friend request to yourself.")

    def mark(self, status):
        self.status = status
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at"])

    def __str__(self):
        return f"{self.sender} -> {self.receiver} ({self.status})"


class Friendship(models.Model):
    user_one = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_started")
    user_two = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(user_one=models.F("user_two")), name="friendship_not_to_self"),
            models.UniqueConstraint(fields=["user_one", "user_two"], name="unique_friendship_pair"),
        ]

    def save(self, *args, **kwargs):
        if self.user_one_id and self.user_two_id and self.user_one_id > self.user_two_id:
            self.user_one_id, self.user_two_id = self.user_two_id, self.user_one_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_one} + {self.user_two}"
