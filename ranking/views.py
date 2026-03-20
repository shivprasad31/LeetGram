from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .models import DailyRanking, GlobalLeaderboard, WeeklyRanking


class LeaderboardPageView(LoginRequiredMixin, TemplateView):
    template_name = "ranking/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["daily_rankings"] = DailyRanking.objects.select_related("user").order_by("rank")[:10]
        context["weekly_rankings"] = WeeklyRanking.objects.select_related("user").order_by("rank")[:10]
        context["global_rankings"] = GlobalLeaderboard.objects.select_related("user").order_by("rank")[:10]
        return context

