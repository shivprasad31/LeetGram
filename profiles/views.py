import json

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.urls import reverse
from django.views.generic import DetailView, UpdateView

from friends.models import Friendship
from groups.models import GroupMembership
from ranking.models import GlobalLeaderboard

from .forms import ProfileUpdateForm
from .models import ProfileStatistics


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
        difficulty_values = [self.object.easy_solved, self.object.medium_solved, self.object.hard_solved]
        global_entry = GlobalLeaderboard.objects.filter(user=user).first()

        context.update(
            {
                "recent_activity": user.activities.all()[:8],
                "recent_solves": user.solved_problems.select_related("problem__difficulty", "problem").all()[:6],
                "friends": friends,
                "friend_count": friendship_qs.count(),
                "groups": memberships[:6],
                "group_count": memberships.count(),
                "global_position": global_entry.rank if global_entry else None,
                "difficulty_labels": json.dumps(["Easy", "Medium", "Hard"]),
                "difficulty_values": json.dumps(difficulty_values),
                "badge_entries": user.badges.select_related("badge")[:4],
                "is_owner": self.request.user.is_authenticated and self.request.user == user,
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

    def get_success_url(self):
        return reverse("profiles:detail", kwargs={"username": self.request.user.username})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        stats = getattr(user, "profile_statistics", None)
        context.update(
            {
                "profile_stats": stats,
            }
        )
        return context
