from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, TemplateView

from .models import Group


class GroupListView(LoginRequiredMixin, TemplateView):
    template_name = "groups/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groups"] = Group.objects.select_related("owner").all()
        return context


class GroupDetailView(LoginRequiredMixin, DetailView):
    model = Group
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "groups/detail.html"
    context_object_name = "group"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        members = self.object.memberships.select_related("user")
        context["members"] = members
        context["member_count"] = members.count()
        return context
