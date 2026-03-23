from django.db.models import Count, Q

from problems.models import UserSolvedProblem

from profiles.models import ProfileStatistics, UserActivity


def log_user_activity(user, activity_type, description, metadata=None):
    return UserActivity.objects.create(
        user=user,
        activity_type=activity_type,
        description=description,
        metadata=metadata or {},
    )


def sync_profile_statistics(user):
    counts = UserSolvedProblem.objects.filter(user=user).aggregate(
        total=Count("id"),
        easy=Count("id", filter=Q(platform_problem__problem__difficulty__slug="easy")),
        medium=Count("id", filter=Q(platform_problem__problem__difficulty__slug="medium")),
        hard=Count("id", filter=Q(platform_problem__problem__difficulty__slug="hard")),
    )
    stats, _ = ProfileStatistics.objects.get_or_create(user=user)
    stats.total_solved = counts["total"] or 0
    stats.easy_solved = counts["easy"] or 0
    stats.medium_solved = counts["medium"] or 0
    stats.hard_solved = counts["hard"] or 0
    stats.save(update_fields=["total_solved", "easy_solved", "medium_solved", "hard_solved"])

    user.solved_count = stats.total_solved
    user.save(update_fields=["solved_count"])
    return stats
