from django.urls import path

from .views import ChallengePageView

app_name = "challenges"

urlpatterns = [
    path("", ChallengePageView.as_view(), name="index"),
]

