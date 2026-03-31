from challenges.consumers import ChallengeRoomConsumer
from django.urls import path

from notifications.consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/challenges/<int:challenge_id>/", ChallengeRoomConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
