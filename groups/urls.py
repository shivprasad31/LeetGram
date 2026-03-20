from django.urls import path

from .views import GroupDetailView, GroupListView

app_name = "groups"

urlpatterns = [
    path("", GroupListView.as_view(), name="index"),
    path("<slug:slug>/", GroupDetailView.as_view(), name="detail"),
]

