from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from problems.models import ProblemDifficulty

from .models import Challenge


class ChallengePageView(LoginRequiredMixin, TemplateView):
    template_name = "challenges/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["challenges"] = Challenge.objects.filter(sender=user) | Challenge.objects.filter(receiver=user)
        context["difficulties"] = ProblemDifficulty.objects.all()
        return context

