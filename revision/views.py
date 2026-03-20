from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from .models import RevisionItem


class RevisionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "revision/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["revision_lists"] = user.revision_lists.prefetch_related("items__problem")
        context["due_items"] = RevisionItem.objects.filter(revision_list__user=user, next_review_at__lte=timezone.now()).select_related("problem")[:10]
        context["notes"] = user.revision_notes.select_related("problem")[:10]
        return context

