from celery import shared_task

from .services import rebuild_global_leaderboard, rebuild_periodic_rankings


@shared_task
def refresh_global_leaderboard():
    rebuild_global_leaderboard()


@shared_task
def refresh_periodic_rankings():
    rebuild_periodic_rankings()

