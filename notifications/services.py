from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from redis.exceptions import RedisError

from .models import Notification


def create_notification(user, title, message, category="system", level="info", actor_user=None, action_url="", payload=None):
    notification = Notification.objects.create(
        user=user,
        actor_user=actor_user,
        title=title,
        message=message,
        category=category,
        level=level,
        action_url=action_url,
        payload=payload or {},
    )
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{user.id}",
            {
                "type": "notification.message",
                "notification": {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "category": notification.category,
                    "level": notification.level,
                    "action_url": notification.action_url,
                },
            },
        )
    except (RedisError, OSError):
        # Persist notifications even when the realtime transport is unavailable.
        pass
    return notification