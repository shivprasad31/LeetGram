from django.urls import path

from .views import AddSolvedProblemView, ProblemDetailView, ProblemListView

app_name = "problems"

urlpatterns = [
    path("", ProblemListView.as_view(), name="index"),
    path("add/", AddSolvedProblemView.as_view(), name="add-solved"),
    path("<slug:slug>/", ProblemDetailView.as_view(), name="detail"),
]
