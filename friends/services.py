from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notifications.services import create_notification
from profiles.services import log_user_activity

from .models import FriendRequest, Friendship


@transaction.atomic
def send_friend_request(sender, receiver, message=""):
    if sender == receiver:
        raise ValidationError("You cannot send yourself a friend request.")
    if Friendship.objects.filter(user_one=min(sender, receiver, key=lambda user: user.id), user_two=max(sender, receiver, key=lambda user: user.id)).exists():
        raise ValidationError("You are already friends.")
    request, created = FriendRequest.objects.get_or_create(
        sender=sender,
        receiver=receiver,
        status="pending",
        defaults={"message": message},
    )
    if not created:
        raise ValidationError("A pending request already exists.")
    create_notification(receiver, "New friend request", f"{sender.username} sent you a friend request.", category="friend", actor_user=sender, action_url="/friends/")
    log_user_activity(sender, "friend", f"Sent a friend request to {receiver.username}", {"receiver_id": receiver.id})
    return request


@transaction.atomic
def accept_friend_request(friend_request):
    friend_request.mark("accepted")
    Friendship.objects.get_or_create(user_one=min(friend_request.sender, friend_request.receiver, key=lambda user: user.id), user_two=max(friend_request.sender, friend_request.receiver, key=lambda user: user.id))
    create_notification(friend_request.sender, "Friend request accepted", f"{friend_request.receiver.username} accepted your request.", category="friend", actor_user=friend_request.receiver, action_url="/friends/")
    log_user_activity(friend_request.sender, "friend", f"Became friends with {friend_request.receiver.username}", {"friend_id": friend_request.receiver.id})
    log_user_activity(friend_request.receiver, "friend", f"Became friends with {friend_request.sender.username}", {"friend_id": friend_request.sender.id})
    return friend_request


@transaction.atomic
def remove_friendship(user, friend):
    user_one, user_two = sorted([user, friend], key=lambda current: current.id)
    deleted, _ = Friendship.objects.filter(user_one=user_one, user_two=user_two).delete()
    if deleted:
        create_notification(friend, "Friend removed", f"{user.username} removed the friendship.", category="friend", actor_user=user, action_url="/friends/")
        log_user_activity(user, "friend", f"Removed {friend.username} from friends", {"friend_id": friend.id})
    return deleted

