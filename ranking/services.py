from django.db.models import Count
from django.utils import timezone

from challenges.models import Challenge
from users.models import User

from .models import DailyRanking, GlobalLeaderboard, WeeklyRanking


def score_breakdown_for_user(user):
    challenges_won = Challenge.objects.filter(winner=user, status="finished").count()
    contest_points = 0
    solved_points = user.solved_count * 2
    streak_bonus = user.streak * 5
    total = challenges_won * 25 + contest_points + solved_points + streak_bonus
    return {
        "score": total,
        "challenges_won": challenges_won,
        "contest_points": contest_points,
        "solved_points": solved_points,
        "streak_bonus": streak_bonus,
    }


def rebuild_global_leaderboard():
    leaders = []
    for user in User.objects.all():
        breakdown = score_breakdown_for_user(user)
        leaders.append((breakdown["score"], user, breakdown))
    leaders.sort(key=lambda item: (-item[0], -item[1].solved_count, -item[1].streak, item[1].username))

    for index, (_, user, breakdown) in enumerate(leaders, start=1):
        GlobalLeaderboard.objects.update_or_create(
            user=user,
            defaults={
                "score": breakdown["score"],
                "total_solved": user.solved_count,
                "challenges_won": breakdown["challenges_won"],
                "rank": index,
            },
        )
    return leaders


def rebuild_periodic_rankings(target_date=None):
    target_date = target_date or timezone.localdate()
    week_start = target_date - timezone.timedelta(days=target_date.weekday())
    DailyRanking.objects.filter(date=target_date).delete()
    WeeklyRanking.objects.filter(week_start=week_start).delete()

    leaders = rebuild_global_leaderboard()
    for index, (_, user, breakdown) in enumerate(leaders, start=1):
        DailyRanking.objects.create(
            date=target_date,
            user=user,
            score=breakdown["score"],
            challenges_won=breakdown["challenges_won"],
            contest_points=breakdown["contest_points"],
            solved_points=breakdown["solved_points"],
            streak_bonus=breakdown["streak_bonus"],
            rank=index,
        )
        WeeklyRanking.objects.create(
            week_start=week_start,
            user=user,
            score=breakdown["score"],
            challenges_won=breakdown["challenges_won"],
            contest_points=breakdown["contest_points"],
            solved_points=breakdown["solved_points"],
            streak_bonus=breakdown["streak_bonus"],
            rank=index,
        )
