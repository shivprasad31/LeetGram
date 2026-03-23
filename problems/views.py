from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from .forms import SolvedProblemForm
from .models import Problem, ProblemDifficulty, Tag
from .services import create_manual_solved_problem


class ProblemListView(ListView):
    model = Problem
    template_name = "problems/index.html"
    context_object_name = "problems"
    paginate_by = 12

    def get_queryset(self):
        queryset = Problem.objects.select_related("difficulty").prefetch_related("tags").all()
        difficulty = self.request.GET.get("difficulty")
        tag = self.request.GET.get("tag")
        search = self.request.GET.get("search")
        if difficulty:
            queryset = queryset.filter(difficulty__slug=difficulty)
        if tag:
            queryset = queryset.filter(tags__slug=tag)
        if search:
            queryset = queryset.filter(canonical_name__icontains=search)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["difficulties"] = ProblemDifficulty.objects.all()
        context["tags"] = Tag.objects.all()[:20]
        return context


class ProblemDetailView(DetailView):
    model = Problem
    slug_field = "slug"
    slug_url_kwarg = "slug"
    template_name = "problems/detail.html"
    context_object_name = "problem"


class AddSolvedProblemView(LoginRequiredMixin, FormView):
    template_name = "problems/add_solved.html"
    form_class = SolvedProblemForm
    success_url = reverse_lazy("dashboard:dashboard")

    def form_valid(self, form):
        create_manual_solved_problem(self.request.user, form.cleaned_data)
        return super().form_valid(form)
