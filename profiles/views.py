import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, TemplateView, UpdateView

from friends.models import Friendship
from groups.models import GroupMembership
from integrations.services import PlatformServiceError
from problems.models import UserSolvedProblem
from users.tasks import dispatch_user_sync

from .forms import ProfileIntegrationForm, ProfileUpdateForm
from .integrations import INTEGRATION_PLATFORMS, build_integration_rows, get_integration_payload
from .models import ProfileStatistics
from .services import log_user_activity, sync_profile_statistics

User = get_user_model()

PLATFORM_LABELS = {
    "leetcode": "LeetCode",
    "codeforces": "Codeforces",
    "gfg": "GeeksforGeeks",
    "hackerrank": "HackerRank",
}


def solved_problem_queryset_for_user(user):
    return UserSolvedProblem.objects.filter(user=user).select_related(
        "platform_problem",
        "platform_problem__problem",
        "platform_problem__problem__difficulty",
    )


def solved_metrics_for_queryset(solved_qs):
    return solved_qs.aggregate(
        total=Count("id"),
        easy=Count("id", filter=Q(platform_problem__problem__difficulty__slug="easy")),
        medium=Count("id", filter=Q(platform_problem__problem__difficulty__slug="medium")),
        hard=Count("id", filter=Q(platform_problem__problem__difficulty__slug="hard")),
    )


class ProfileDetailView(DetailView):
    model = ProfileStatistics
    template_name = "profiles/detail.html"
    context_object_name = "profile_stats"
    slug_field = "user__username"
    slug_url_kwarg = "username"

    def get_queryset(self):
        return ProfileStatistics.objects.select_related("user")

    def get_object(self, queryset=None):
        return self.get_queryset().get(user__username=self.kwargs["username"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object.user
        friendship_qs = Friendship.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related("user_one", "user_two")
        memberships = GroupMembership.objects.filter(user=user).select_related("group")
        friends = [relation.user_two if relation.user_one == user else relation.user_one for relation in friendship_qs[:6]]
        solved_qs = solved_problem_queryset_for_user(user)
        counts = solved_metrics_for_queryset(solved_qs)
        difficulty_values = [counts["easy"] or 0, counts["medium"] or 0, counts["hard"] or 0]
        today = timezone.localdate()
        today_solved_qs = solved_qs.filter(solved_at__date=today)
        sync_profile_statistics(user)

        overall_platform_breakdown = [
            {
                "label": PLATFORM_LABELS.get(entry["platform_problem__platform"], entry["platform_problem__platform"].title()),
                "count": entry["total"],
            }
            for entry in solved_qs.values("platform_problem__platform").annotate(total=Count("id")).order_by("platform_problem__platform")
            if entry["platform_problem__platform"]
        ]
        today_platform_breakdown = [
            {
                "label": PLATFORM_LABELS.get(entry["platform_problem__platform"], entry["platform_problem__platform"].title()),
                "count": entry["total"],
            }
            for entry in today_solved_qs.values("platform_problem__platform").annotate(total=Count("id")).order_by("platform_problem__platform")
            if entry["platform_problem__platform"]
        ]
        difficulty_breakdown = [
            {
                "label": entry["platform_problem__problem__difficulty__name"] or "Unrated",
                "slug": entry["platform_problem__problem__difficulty__slug"] or "unrated",
                "count": entry["total"],
            }
            for entry in solved_qs.values(
                "platform_problem__problem__difficulty__name",
                "platform_problem__problem__difficulty__slug",
            ).annotate(total=Count("id")).order_by("platform_problem__problem__difficulty__slug")
        ]

        context.update(
            {
                "recent_solves": solved_qs[:6],
                "friends": friends,
                "friend_count": friendship_qs.count(),
                "groups": memberships[:6],
                "group_count": memberships.count(),
                "difficulty_labels": json.dumps(["Easy", "Medium", "Hard"]),
                "difficulty_values": json.dumps(difficulty_values),
                "badge_entries": user.badges.select_related("badge")[:4],
                "is_owner": self.request.user.is_authenticated and self.request.user == user,
                "integration_rows": build_integration_rows(user),
                "today_solved_count": today_solved_qs.count(),
                "overall_solved_count": counts["total"] or 0,
                "easy_solved_count": counts["easy"] or 0,
                "medium_solved_count": counts["medium"] or 0,
                "hard_solved_count": counts["hard"] or 0,
                "today_platform_breakdown": today_platform_breakdown,
                "overall_platform_breakdown": overall_platform_breakdown,
                "difficulty_breakdown": difficulty_breakdown,
                "today_label": today,
            }
        )
        return context


class SolvedQuestionsView(TemplateView):
    template_name = "profiles/solved_questions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = User.objects.get(username=self.kwargs["username"])
        search_query = self.request.GET.get("q", "").strip()
        platform_filter = self.request.GET.get("platform", "").strip().lower()
        difficulty_filter = self.request.GET.get("difficulty", "").strip().lower()

        solved_qs = solved_problem_queryset_for_user(profile_user)
        if search_query:
            solved_qs = solved_qs.filter(
                Q(platform_problem__problem__canonical_name__icontains=search_query)
                | Q(platform_problem__title__icontains=search_query)
            )
        if platform_filter:
            solved_qs = solved_qs.filter(platform_problem__platform=platform_filter)
        if difficulty_filter:
            solved_qs = solved_qs.filter(platform_problem__problem__difficulty__slug=difficulty_filter)

        solved_qs = solved_qs.order_by("-solved_at", "platform_problem__problem__canonical_name")
        total_solved = solved_problem_queryset_for_user(profile_user).count()

        context.update(
            {
                "profile_user": profile_user,
                "solved_questions": solved_qs,
                "solved_total_count": total_solved,
                "filtered_count": solved_qs.count(),
                "search_query": search_query,
                "platform_filter": platform_filter,
                "difficulty_filter": difficulty_filter,
                "platform_options": [
                    ("leetcode", "LeetCode"),
                    ("codeforces", "Codeforces"),
                    ("gfg", "GeeksforGeeks"),
                    ("hackerrank", "HackerRank"),
                ],
                "difficulty_options": [("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")],
            }
        )
        return context


class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    form_class = ProfileUpdateForm
    template_name = "profiles/edit.html"

    def get_object(self, queryset=None):
        return self.request.user

    def test_func(self):
        return self.request.user.username == self.kwargs["username"]

    def form_valid(self, form):
        existing_values = {field_name: getattr(self.request.user, field_name) for field_name in INTEGRATION_PLATFORMS}
        response = super().form_valid(form)
        updated_values = {field_name: getattr(self.request.user, field_name) for field_name in INTEGRATION_PLATFORMS}
        changed_platforms = [
            meta["label"]
            for field_name, meta in INTEGRATION_PLATFORMS.items()
            if existing_values[field_name] != updated_values[field_name]
        ]
        if changed_platforms:
            dispatch_user_sync(self.request.user.id)
            log_user_activity(
                self.request.user,
                "integration",
                "Connected profiles updated from the profile page.",
                {"platforms": changed_platforms},
            )
            messages.success(self.request, "Connected profiles saved. Sync has started.")
        else:
            messages.success(self.request, "Profile updated successfully.")
        return response

    def get_success_url(self):
        return reverse("profiles:detail", kwargs={"username": self.request.user.username})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        stats = getattr(user, "profile_statistics", None)
        context.update(
            {
                "profile_stats": stats,
                "integration_rows": build_integration_rows(user),
            }
        )
        return context


@login_required
@require_POST
def update_profile_integrations(request):
    baseline_user = User.objects.get(pk=request.user.pk)
    current_user = User.objects.get(pk=request.user.pk)
    previous_values = {field_name: getattr(baseline_user, field_name) for field_name in INTEGRATION_PLATFORMS}

    form = ProfileIntegrationForm(request.POST, instance=current_user)
    if not form.is_valid():
        errors = {field_name: [str(message) for message in messages_list] for field_name, messages_list in form.errors.items()}
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "errors": errors, "message": "Please correct the invalid usernames."}, status=400)
        messages.error(request, "Please correct the highlighted profile integration errors.")
        return redirect("profiles:edit", username=request.user.username)

    user = form.save(commit=False)
    updated_fields = [
        field_name
        for field_name in INTEGRATION_PLATFORMS
        if previous_values[field_name] != getattr(user, field_name)
    ]
    if updated_fields:
        user.save(update_fields=updated_fields)
        current_user.refresh_from_db(fields=updated_fields)
        dispatch_user_sync(current_user.id)
        log_user_activity(
            current_user,
            "integration",
            "Connected profiles updated.",
            {"platforms": [INTEGRATION_PLATFORMS[field_name]["label"] for field_name in updated_fields]},
        )
        message = "Connected profiles saved. Sync has started."
    else:
        message = "No connected profile changes were detected."

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": message, **get_integration_payload(current_user)})

    messages.success(request, message)
    return redirect("profiles:edit", username=request.user.username)


@login_required
@require_GET
def get_profiles(request):
    current_user = User.objects.get(pk=request.user.pk)
    return JsonResponse({"ok": True, **get_integration_payload(current_user)})


@login_required
@require_POST
def sync_now(request):
    current_user = User.objects.get(pk=request.user.pk)
    if not current_user.has_connected_profiles:
        return JsonResponse({"ok": False, "message": "Connect at least one platform before syncing."}, status=400)

    try:
        sync_result = dispatch_user_sync(current_user.id, force_sync=True)
    except PlatformServiceError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)
    except Exception:
        return JsonResponse({"ok": False, "message": "Profile sync could not be completed right now. Please try again shortly."}, status=500)

    current_user.refresh_from_db(fields=["last_synced_at"])
    created_count = ((sync_result.get("result") or {}).get("created_count")) or 0
    if created_count:
        message = f"Profile sync completed. {created_count} new solved problem{'s' if created_count != 1 else ''} imported."
    else:
        message = "Profile sync completed. No new solved problems were found."
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "message": message, **get_integration_payload(current_user)})

    messages.success(request, message)
    return redirect("profiles:edit", username=request.user.username)
