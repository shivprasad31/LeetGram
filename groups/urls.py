from django.urls import path

from .views import (
    GroupDashboardView,
    GroupDetailView,
    accept_invite,
    add_group_task,
    create_group,
    get_group_details,
    get_user_groups,
    reject_invite,
    send_challenge,
    send_invite,
)

app_name = "groups"

urlpatterns = [
    path("", GroupDashboardView.as_view(), name="index"),
    path("create/", create_group, name="create"),
    path("invite/send/", send_invite, name="send_invite"),
    path("invite/<int:invite_id>/accept/", accept_invite, name="accept_invite"),
    path("invite/<int:invite_id>/reject/", reject_invite, name="reject_invite"),
    path("tasks/add/", add_group_task, name="add_task"),
    path("challenge/send/", send_challenge, name="send_challenge"),
    path("api/list/", get_user_groups, name="get_user_groups"),
    path("api/<slug:slug>/", get_group_details, name="get_group_details"),
    path("<slug:slug>/", GroupDetailView.as_view(), name="detail"),
]