from itertools import chain
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import RedirectView, TemplateView

from friends.models import Friendship
from notifications.services import create_notification
from problems.models import Problem
from profiles.services import log_user_activity
from users.models import User

from .models import Group, GroupChallenge, GroupInvite, GroupMembership, GroupTask


def _friend_users_for(user):
    friendships = Friendship.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related("user_one", "user_two")
    friends = []
    for friendship in friendships:
        friends.append(friendship.user_two if friendship.user_one == user else friendship.user_one)
    return sorted(friends, key=lambda friend: friend.username.lower())


def _group_queryset_for(user):
    return (
        Group.objects.filter(memberships__user=user)
        .select_related("owner")
        .annotate(member_total=Count("memberships", distinct=True))
        .prefetch_related("memberships__user")
        .distinct()
    )


def _selected_group_for(user, slug):
    if not slug:
        return None
    return get_object_or_404(_group_queryset_for(user), slug=slug)


def _activity_feed_for(group):
    if not group:
        return []

    task_entries = [
        {
            "created_at": task.created_at,
            "label": f"{task.created_by.username} added a new question",
            "meta": task.title,
            "type": "task",
        }
        for task in group.tasks.select_related("created_by")[:6]
    ]
    challenge_entries = [
        {
            "created_at": challenge.created_at,
            "label": f"{challenge.challenger.username} challenged {challenge.opponent.username}",
            "meta": challenge.problem.canonical_name if challenge.problem else challenge.get_status_display(),
            "type": "challenge",
        }
        for challenge in group.group_challenges.select_related("challenger", "opponent", "problem")[:6]
    ]
    entries = sorted(chain(task_entries, challenge_entries), key=lambda item: item["created_at"], reverse=True)
    return entries[:8]


def _group_detail_payload(group, current_user):
    members = list(group.memberships.select_related("user").order_by("role", "user__username"))
    tasks = list(group.tasks.select_related("created_by")[:8])
    challenges = list(group.group_challenges.select_related("challenger", "opponent", "problem")[:8])
    return {
        "slug": group.slug,
        "name": group.name,
        "description": group.description,
        "member_count": group.member_count,
        "is_admin": group.is_admin(current_user),
        "members": [
            {
                "username": membership.user.username,
                "role": membership.role,
            }
            for membership in members
        ],
        "tasks": [
            {
                "title": task.title,
                "description": task.description,
                "difficulty": task.difficulty,
                "link": task.link,
                "created_by": task.created_by.username,
            }
            for task in tasks
        ],
        "challenges": [
            {
                "challenger": challenge.challenger.username,
                "opponent": challenge.opponent.username,
                "status": challenge.status,
                "problem": challenge.problem.canonical_name if challenge.problem else "",
            }
            for challenge in challenges
        ],
        "activity": _activity_feed_for(group),
    }


class GroupDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "groups/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        groups = list(_group_queryset_for(user))
        requested_slug = self.request.GET.get("group", "").strip()
        selected_group = _selected_group_for(user, requested_slug) if requested_slug else (groups[0] if groups else None)
        selected_membership = None
        selected_members = []
        selected_tasks = []
        selected_challenges = []
        selected_activity = []
        selected_group_friend_options = []
        problem_options = Problem.objects.select_related("difficulty").all()[:30]
        friend_options = _friend_users_for(user)
        pending_invites = GroupInvite.objects.filter(invitee=user, status="pending").select_related("group", "invited_by")

        if selected_group:
            selected_members = list(selected_group.memberships.select_related("user").order_by("role", "user__username"))
            selected_membership = next((membership for membership in selected_members if membership.user_id == user.id), None)
            selected_tasks = list(selected_group.tasks.select_related("created_by")[:8])
            selected_challenges = list(selected_group.group_challenges.select_related("challenger", "opponent", "problem")[:8])
            selected_activity = _activity_feed_for(selected_group)
            existing_member_ids = {membership.user_id for membership in selected_members}
            selected_group_friend_options = [friend for friend in friend_options if friend.id not in existing_member_ids]

        context.update(
            {
                "groups": groups,
                "selected_group": selected_group,
                "selected_membership": selected_membership,
                "selected_members": selected_members,
                "selected_tasks": selected_tasks,
                "selected_challenges": selected_challenges,
                "selected_activity": selected_activity,
                "pending_invites": pending_invites,
                "friend_options": friend_options,
                "selected_group_friend_options": selected_group_friend_options,
                "problem_options": problem_options,
                "selected_group_is_admin": selected_group.is_admin(user) if selected_group else False,
            }
        )
        return context


class GroupDetailView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return f"{reverse('groups:index')}?{urlencode({'group': kwargs['slug']})}"


@login_required
@require_POST
@transaction.atomic
def create_group(request):
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    selected_friend_ids = {int(friend_id) for friend_id in request.POST.getlist("friend_ids") if friend_id.isdigit()}
    valid_friend_ids = {friend.id for friend in _friend_users_for(request.user)}

    if not name:
        messages.error(request, "Group name is required.")
        return redirect("groups:index")

    group = Group.objects.create(name=name, description=description, owner=request.user, privacy="invite_only")
    GroupMembership.objects.get_or_create(group=group, user=request.user, defaults={"role": "owner"})

    for friend_id in sorted(selected_friend_ids & valid_friend_ids):
        invitee = User.objects.get(pk=friend_id)
        invite, created = GroupInvite.objects.get_or_create(
            group=group,
            invitee=invitee,
            status="pending",
            defaults={"invited_by": request.user},
        )
        if created:
            create_notification(invitee, "New group invite", f"{request.user.username} invited you to {group.name}.", category="group", actor_user=request.user, action_url=f"/groups/?group={group.slug}")

    log_user_activity(request.user, "group", f"Created group {group.name}", {"group_slug": group.slug})
    messages.success(request, f"{group.name} created successfully.")
    return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")


@login_required
@require_POST
def send_invite(request):
    group = _selected_group_for(request.user, request.POST.get("group_slug", "").strip())
    if not group or not group.is_admin(request.user):
        raise PermissionDenied

    friend_id = request.POST.get("friend_id", "").strip()
    friend = get_object_or_404(User, pk=friend_id)
    valid_friend_ids = {item.id for item in _friend_users_for(request.user)}
    if friend.id not in valid_friend_ids:
        messages.error(request, "Only friends can be invited to a group.")
        return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")

    try:
        invite = GroupInvite(group=group, invited_by=request.user, invitee=friend)
        invite.full_clean()
        invite.save()
        create_notification(friend, "New group invite", f"{request.user.username} invited you to {group.name}.", category="group", actor_user=request.user, action_url=f"/groups/?group={group.slug}")
        messages.success(request, f"Invitation sent to {friend.username}.")
    except ValidationError as exc:
        messages.error(request, exc.message if hasattr(exc, "message") else exc.messages[0])

    return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")


@login_required
@require_POST
@transaction.atomic
def accept_invite(request, invite_id):
    invite = get_object_or_404(GroupInvite.objects.select_related("group", "invited_by"), pk=invite_id, invitee=request.user, status="pending")
    invite.accept()
    create_notification(invite.invited_by, "Group invite accepted", f"{request.user.username} joined {invite.group.name}.", category="group", actor_user=request.user, action_url=f"/groups/?group={invite.group.slug}")
    log_user_activity(request.user, "group", f"Joined group {invite.group.name}", {"group_slug": invite.group.slug})
    messages.success(request, f"You joined {invite.group.name}.")
    return redirect(f"{reverse('groups:index')}?{urlencode({'group': invite.group.slug})}")


@login_required
@require_POST
def reject_invite(request, invite_id):
    invite = get_object_or_404(GroupInvite.objects.select_related("group"), pk=invite_id, invitee=request.user, status="pending")
    invite.reject()
    messages.info(request, f"Invitation to {invite.group.name} rejected.")
    return redirect("groups:index")


@login_required
@require_POST
def add_group_task(request):
    group = _selected_group_for(request.user, request.POST.get("group_slug", "").strip())
    if not group or not group.is_admin(request.user):
        raise PermissionDenied

    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Task title is required.")
        return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")

    task = GroupTask.objects.create(
        group=group,
        created_by=request.user,
        title=title,
        description=request.POST.get("description", "").strip(),
        difficulty=request.POST.get("difficulty", "").strip(),
        link=request.POST.get("link", "").strip(),
    )
    for membership in group.memberships.exclude(user=request.user).select_related("user"):
        create_notification(membership.user, "New group task", f"{request.user.username} added {task.title} in {group.name}.", category="group", actor_user=request.user, action_url=f"/groups/?group={group.slug}")
    log_user_activity(request.user, "group", f"Added task {task.title} in {group.name}", {"group_slug": group.slug})
    messages.success(request, "Task added to the group.")
    return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")


@login_required
@require_POST
def send_challenge(request):
    group = _selected_group_for(request.user, request.POST.get("group_slug", "").strip())
    if not group:
        raise PermissionDenied

    opponent = get_object_or_404(User, pk=request.POST.get("opponent_id"), group_memberships__group=group)
    if opponent == request.user:
        messages.error(request, "You cannot challenge yourself.")
        return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")

    problem = None
    problem_id = request.POST.get("problem_id", "").strip()
    if problem_id.isdigit():
        problem = Problem.objects.filter(pk=problem_id).first()

    challenge = GroupChallenge.objects.create(group=group, challenger=request.user, opponent=opponent, problem=problem)
    create_notification(opponent, "New group challenge", f"{request.user.username} challenged you in {group.name}.", category="challenge", actor_user=request.user, action_url=f"/groups/?group={group.slug}")
    log_user_activity(request.user, "challenge", f"Challenged {opponent.username} in {group.name}", {"group_slug": group.slug, "opponent_id": opponent.id})
    messages.success(request, f"Challenge sent to {opponent.username}.")
    return redirect(f"{reverse('groups:index')}?{urlencode({'group': group.slug})}")


@login_required
@require_GET
def get_user_groups(request):
    payload = [
        {
            "slug": group.slug,
            "name": group.name,
            "member_count": group.member_total,
            "owner": group.owner.username,
        }
        for group in _group_queryset_for(request.user)
    ]
    return JsonResponse({"groups": payload})


@login_required
@require_GET
def get_group_details(request, slug):
    group = _selected_group_for(request.user, slug)
    return JsonResponse({"group": _group_detail_payload(group, request.user)})