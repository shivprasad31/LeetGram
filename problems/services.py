from django.db import models, transaction
from django.utils import timezone
from .models import Problem, UserSolvedProblem, ProblemDifficulty, Tag, PlatformProblem
from profiles.services import log_user_activity
from revision.services import enqueue_problem_for_revision

STANDARD_DIFFICULTIES = {
    "easy": {"name": "Easy", "weight": 1, "color": "#4ECDC4"},
    "medium": {"name": "Medium", "weight": 2, "color": "#FFE66D"},
    "hard": {"name": "Hard", "weight": 3, "color": "#FF6B6B"},
}


def normalize_difficulty_value(value):
    normalized = (value or "").strip().lower()
    return normalized if normalized in STANDARD_DIFFICULTIES else "medium"


def get_standard_difficulty(value="medium"):
    slug = normalize_difficulty_value(value)
    defaults = STANDARD_DIFFICULTIES[slug]
    difficulty, _ = ProblemDifficulty.objects.get_or_create(
        slug=slug,
        defaults={"name": defaults["name"], "weight": defaults["weight"], "color": defaults["color"]},
    )
    changed_fields = []
    if difficulty.name != defaults["name"]:
        difficulty.name = defaults["name"]
        changed_fields.append("name")
    if difficulty.weight != defaults["weight"]:
        difficulty.weight = defaults["weight"]
        changed_fields.append("weight")
    if difficulty.color != defaults["color"]:
        difficulty.color = defaults["color"]
        changed_fields.append("color")
    if changed_fields:
        difficulty.save(update_fields=changed_fields)
    return difficulty


def ensure_problem_difficulty(problem, value=None):
    if problem.difficulty_id and problem.difficulty.slug in STANDARD_DIFFICULTIES:
        return problem.difficulty
    difficulty = get_standard_difficulty(value)
    if problem.difficulty_id != difficulty.id:
        problem.difficulty = difficulty
        problem.save(update_fields=["difficulty"])
    return difficulty


def recommend_problems_for_user(user, limit=6):
    # 1. Get solved problems and their tags
    solved_problems = user.solved_problems.all()
    solved_ids = solved_problems.values_list("platform_problem__problem_id", flat=True)
    
    # Identify most frequent tags for the user
    user_tags = Tag.objects.filter(
        problems__platform_problems__solvers__user=user
    ).annotate(
        count=models.Count("id")
    ).order_by("-count")
    
    top_tag_ids = [tag.id for tag in user_tags[:10]]
    
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
        difficulty = problem.difficulty or get_standard_difficulty()
        score = affinity * 5 + difficulty.weight * 2
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
    
    # 1. Create or get the canonical Problem
    problem, created = Problem.objects.get_or_create(
        canonical_name=data["title"],
        defaults={
            "statement": data.get("statement", ""),
            "difficulty": difficulty,
        }
    )
    
    if tags:
        problem.tags.set(tags)
    ensure_problem_difficulty(problem, getattr(difficulty, "slug", None))
        
    # 2. Create or get the PlatformProblem (custom platform)
    platform_problem, _ = PlatformProblem.objects.get_or_create(
        platform="custom",
        platform_id=f"manual-{timezone.now().timestamp()}",
        defaults={
            "title": data["title"],
            "url": data.get("url", ""),
            "problem": problem,
        }
    )
    
    # 3. Create the UserSolvedProblem
    solved_problem, _ = UserSolvedProblem.objects.get_or_create(
        user=user,
        platform_problem=platform_problem,
        defaults={
            "solved_at": timezone.now(),
            "notes": notes,
        }
    )
    
    enqueue_problem_for_revision(user, problem, next_review_at=timezone.now() + timezone.timedelta(days=1))
    
    log_user_activity(user, "problem", f"Manually added solved problem: {problem.canonical_name}", {"problem_id": problem.id})
    return solved_problem
