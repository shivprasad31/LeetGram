from django.urls import path

from .views import LeaderboardPageView

app_name = "ranking"

urlpatterns = [
    path("", LeaderboardPageView.as_view(), name="index"),
]

