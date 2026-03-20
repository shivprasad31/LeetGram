import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, TemplateView

from .models import Contest


class ContestListView(LoginRequiredMixin, TemplateView):
    template_name = "contests/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contests"] = Contest.objects.select_related("host", "difficulty", "group").all()
        return context


class ContestDetailView(LoginRequiredMixin, DetailView):
    model = Contest
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "contests/detail.html"
    context_object_name = "contest"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contest = self.object
        context["leaderboard"] = contest.leaderboard_entries.select_related("participant__user", "team")
        chart_labels = []
        chart_values = []
        for entry in context["leaderboard"][:8]:
            label = entry.team.name if entry.team else entry.participant.user.username
            chart_labels.append(label)
            chart_values.append(entry.score)
        context["leaderboard_labels"] = json.dumps(chart_labels)
        context["leaderboard_values"] = json.dumps(chart_values)
        return context

