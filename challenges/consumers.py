import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from .models import Challenge


class ChallengeRoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user", AnonymousUser())
        if not user.is_authenticated:
            await self.close()
            return

        self.challenge_id = self.scope["url_route"]["kwargs"]["challenge_id"]
        is_participant = await Challenge.objects.filter(id=self.challenge_id).filter(
            Q(challenger_id=user.id) | Q(opponent_id=user.id)
        ).aexists()
        if not is_participant:
            await self.close()
            return

        self.room_group_name = f"challenge_{self.challenge_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def challenge_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "challenge_id": event["challenge_id"],
                    "status": event.get("status", ""),
                    "refresh": True,
                }
            )
        )
