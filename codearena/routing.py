from django.urls import path

from contests.consumers import ContestLeaderboardConsumer
from notifications.consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/contests/<int:contest_id>/leaderboard/", ContestLeaderboardConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]

