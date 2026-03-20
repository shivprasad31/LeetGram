from django.urls import path

from .views import ProfileDetailView, ProfileUpdateView

app_name = "profiles"

urlpatterns = [
    path("<str:username>/edit/", ProfileUpdateView.as_view(), name="edit"),
    path("<str:username>/", ProfileDetailView.as_view(), name="detail"),
]
