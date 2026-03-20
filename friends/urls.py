from django.urls import path

from .views import FriendsPageView

app_name = "friends"

urlpatterns = [
    path("", FriendsPageView.as_view(), name="index"),
]

