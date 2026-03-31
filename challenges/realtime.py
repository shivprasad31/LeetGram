from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from redis.exceptions import RedisError


def broadcast_challenge_update(challenge):
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"challenge_{challenge.id}",
            {
                "type": "challenge.message",
                "challenge_id": challenge.id,
                "status": challenge.status,
            },
        )
    except (RedisError, OSError, AttributeError):
        pass
