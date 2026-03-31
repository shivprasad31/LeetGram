from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from problems.models import Tag, UserSolvedProblem

from .models import RevisionNote


class RevisionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "revision/index.html"
    paginate_by = 15

    def _base_queryset(self):
        return (
            UserSolvedProblem.objects.filter(user=self.request.user)
            .select_related(
                "platform_problem",
                "platform_problem__problem",
                "platform_problem__problem__difficulty",
            )
            .prefetch_related(
                Prefetch("platform_problem__problem__tags", queryset=Tag.objects.order_by("name"))
            )
            .order_by("-solved_at", "platform_problem__problem__canonical_name")
        )

    def _filtered_queryset(self):
        queryset = self._base_queryset()
        search = self.request.GET.get("search", "").strip()
        platform = self.request.GET.get("platform", "").strip()
        difficulty = self.request.GET.get("difficulty", "").strip()
        topic = self.request.GET.get("topic", "").strip()

        if search:
            queryset = queryset.filter(
                Q(platform_problem__problem__canonical_name__icontains=search)
                | Q(platform_problem__title__icontains=search)
            )
        if platform:
            queryset = queryset.filter(platform_problem__platform=platform)
        if difficulty:
            queryset = queryset.filter(platform_problem__problem__difficulty__slug=difficulty)
        if topic:
            queryset = queryset.filter(platform_problem__problem__tags__slug=topic)
        return queryset.distinct()

    def post(self, request, *args, **kwargs):
        problem_id = request.POST.get("problem_id")
        note_text = (request.POST.get("note_text") or "").strip()
        allowed_problem_ids = set(self._base_queryset().values_list("platform_problem__problem_id", flat=True))
        try:
            problem_id = int(problem_id)
        except (TypeError, ValueError) as exc:
            raise Http404 from exc
        if problem_id not in allowed_problem_ids:
            raise Http404
        if note_text:
            RevisionNote.objects.update_or_create(
                user=request.user,
                problem_id=problem_id,
                defaults={"note_text": note_text},
            )
            messages.success(request, "Revision note saved.")
        else:
            RevisionNote.objects.filter(user=request.user, problem_id=problem_id).delete()
            messages.info(request, "Revision note cleared.")
        redirect_url = reverse("revision:index")
        query_string = request.GET.urlencode()
        return redirect(f"{redirect_url}?{query_string}" if query_string else redirect_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self._filtered_queryset()
        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        problem_ids = [item.platform_problem.problem_id for item in page_obj.object_list if item.platform_problem_id and item.platform_problem.problem_id]
        note_map = {
            note.problem_id: note.note_text
            for note in RevisionNote.objects.filter(user=self.request.user, problem_id__in=problem_ids)
        }
        for item in page_obj.object_list:
            item.revision_note_text = note_map.get(item.platform_problem.problem_id, "")

        available_base = self._base_queryset()
        context.update(
            {
                "page_obj": page_obj,
                "solved_page": page_obj.object_list,
                "search_query": self.request.GET.get("search", "").strip(),
                "selected_platform": self.request.GET.get("platform", "").strip(),
                "selected_difficulty": self.request.GET.get("difficulty", "").strip(),
                "selected_topic": self.request.GET.get("topic", "").strip(),
                "platform_options": list(
                    available_base.values_list("platform_problem__platform", flat=True).distinct().order_by("platform_problem__platform")
                ),
                "difficulty_options": list(
                    available_base.exclude(platform_problem__problem__difficulty__isnull=True)
                    .values(
                        "platform_problem__problem__difficulty__slug",
                        "platform_problem__problem__difficulty__name",
                    )
                    .distinct()
                    .order_by("platform_problem__problem__difficulty__name")
                ),
                "topic_options": list(
                    Tag.objects.filter(problems__platform_problems__solvers__user=self.request.user)
                    .distinct()
                    .order_by("name")
                ),
            }
        )
        return context
