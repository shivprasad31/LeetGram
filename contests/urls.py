from django.urls import path

from .views import ContestDetailView, ContestListView

app_name = "contests"

urlpatterns = [
    path("", ContestListView.as_view(), name="index"),
    path("<slug:slug>/", ContestDetailView.as_view(), name="detail"),
]

