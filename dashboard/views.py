import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from challenges.models import Challenge
from contests.models import Contest
from problems.services import recommend_problems_for_user
from ranking.services import score_breakdown_for_user
from users.models import User


@method_decorator(never_cache, name="dispatch")
class LandingPageView(TemplateView):
    template_name = "dashboard/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["top_coders"] = User.objects.order_by("-rating")[:6]
        context["trending_challenges"] = Challenge.objects.select_related("sender", "receiver").order_by("-created_at")[:5]
        context["active_contests"] = Contest.objects.select_related("host").order_by("start_at")[:4]
        return context


@method_decorator(never_cache, name="dispatch")
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        breakdown = score_breakdown_for_user(user)
        recommended = recommend_problems_for_user(user)
        recommendation_labels = [problem.title for problem in recommended]
        recommendation_values = [problem.points for problem in recommended]
        context.update(
            {
                "score_breakdown": breakdown,
                "recommended_problems": recommended,
                "active_challenges": Challenge.objects.filter(receiver=user).exclude(status="finished")[:5],
                "upcoming_contests": Contest.objects.order_by("start_at")[:5],
                "global_position": getattr(getattr(user, "global_leaderboard", None), "rank", None),
                "chart_labels": json.dumps(recommendation_labels),
                "chart_values": json.dumps(recommendation_values),
            }
        )
        return context
