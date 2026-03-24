from django.urls import path

from .views import (
    ChallengePageView,
    ChallengeRoomView,
    accept_challenge_view,
    reject_challenge_view,
    send_challenge_view,
)

app_name = "challenges"

urlpatterns = [
    path("", ChallengePageView.as_view(), name="index"),
    path("send/", send_challenge_view, name="send"),
    path("<int:challenge_id>/accept/", accept_challenge_view, name="accept"),
    path("<int:challenge_id>/reject/", reject_challenge_view, name="reject"),
    path("<int:pk>/room/", ChallengeRoomView.as_view(), name="room"),
]
