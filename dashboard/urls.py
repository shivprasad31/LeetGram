from django.urls import path

from .views import DashboardView, LandingPageView

app_name = "dashboard"

urlpatterns = [
    path("", LandingPageView.as_view(), name="landing"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
]
