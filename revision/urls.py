from django.urls import path

from .views import RevisionDashboardView

app_name = "revision"

urlpatterns = [
    path("", RevisionDashboardView.as_view(), name="index"),
]

