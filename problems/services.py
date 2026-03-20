from django.db import models, transaction
from django.utils import timezone
from .models import Problem, UserSolvedProblem, ProblemDifficulty, ProblemTag
from profiles.services import log_user_activity
from revision.models import RevisionList, RevisionItem


def recommend_problems_for_user(user, limit=6):
    # 1. Get solved problems and their tags
    solved_problems = user.solved_problems.all()
    solved_ids = solved_problems.values_list("problem_id", flat=True)
    
    # Identify most frequent tags for the user
    user_tags = Problem.tags.through.objects.filter(
        problem__solvers__user=user
    ).values("problemtag_id").annotate(
        count=models.Count("problemtag_id")
    ).order_by("-count")
    
    top_tag_ids = [item["problemtag_id"] for item in user_tags[:10]]
    
    # 2. Find candidates that have at least one of the user's top tags
    if top_tag_ids:
        candidate_qs = Problem.objects.filter(
            tags__id__in=top_tag_ids
        ).exclude(
            id__in=solved_ids
        )
    else:
        # Fallback if user has no solved problems
        candidate_qs = Problem.objects.exclude(id__in=solved_ids)

    # 3. Rank a limited subset of candidates (e.g. 50-100) to keep memory usage low
    candidates = candidate_qs.select_related("difficulty").prefetch_related("tags").distinct()[:50]

    ranked = []
    for problem in candidates:
        # Simple affinity score based on tag overlap
        affinity = sum(1 for tag in problem.tags.all() if tag.id in top_tag_ids)
        score = affinity * 5 + problem.difficulty.weight * 2
        ranked.append((score, problem))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [problem for _, problem in ranked[:limit]]


@transaction.atomic
def create_manual_solved_problem(user, data):
    """
    Creates a Problem and UserSolvedProblem from manual input.
    Also creates a RevisionItem.
    """
    tags = data.pop("tags", [])
    difficulty = data.pop("difficulty")
    notes = data.pop("notes", "")
    
    # 1. Create or get the Problem
    problem, created = Problem.objects.get_or_create(
        title=data["title"],
        platform="custom",
        defaults={
            "statement": data.get("statement", ""),
            "url": data.get("url", ""),
            "difficulty": difficulty,
            "points": 100,
        }
    )
    
    if tags:
        problem.tags.set(tags)
    
    # 2. Create the UserSolvedProblem
    solved_problem, _ = UserSolvedProblem.objects.get_or_create(
        user=user,
        problem=problem,
        defaults={
            "platform": "custom",
            "solved_at": timezone.now(),
            "notes": notes,
        }
    )
    
    # 3. Create a RevisionItem
    revision_list = user.revision_lists.filter(is_default=True).first() or user.revision_lists.first()
    if not revision_list:
        revision_list = RevisionList.objects.create(user=user, title="Default Revision List", is_default=True)
    
    RevisionItem.objects.get_or_create(
        revision_list=revision_list,
        problem=problem,
        defaults={
            "next_review_at": timezone.now() + timezone.timedelta(days=1),
        }
    )
    
    log_user_activity(user, "problem", f"Manually added solved problem: {problem.title}", {"problem_id": problem.id})
    return solved_problem
