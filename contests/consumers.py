import json

from channels.generic.websocket import AsyncWebsocketConsumer


class ContestLeaderboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.contest_id = self.scope["url_route"]["kwargs"]["contest_id"]
        self.room_group_name = f"contest_{self.contest_id}_leaderboard"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def leaderboard_message(self, event):
        await self.send(text_data=json.dumps({"contest_id": event["contest_id"], "refresh": True}))

