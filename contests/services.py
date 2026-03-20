from collections import defaultdict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from profiles.services import log_user_activity

from .models import ContestLeaderboard


@transaction.atomic
def rebuild_contest_leaderboard(contest):
    submissions = contest.submissions.select_related("participant", "team", "problem").order_by("submitted_at")
    buckets = defaultdict(lambda: {"score": 0, "penalty": 0, "last_submission_at": None})
    solved_by_problem = defaultdict(dict)

    for submission in submissions:
        entrant_key = submission.team_id if contest.is_team_based else submission.participant_id
        if entrant_key is None:
            continue
        bucket = buckets[entrant_key]
        current_best = solved_by_problem[entrant_key].get(submission.problem_id, 0)
        if submission.score > current_best:
            bucket["score"] += submission.score - current_best
            solved_by_problem[entrant_key][submission.problem_id] = submission.score
        if submission.verdict != "accepted":
            bucket["penalty"] += 20
        if contest.start_at:
            bucket["penalty"] += max(0, int((submission.submitted_at - contest.start_at).total_seconds() // 60))
        bucket["last_submission_at"] = submission.submitted_at

    ordered = sorted(buckets.items(), key=lambda item: (-item[1]["score"], item[1]["penalty"]))
    ContestLeaderboard.objects.filter(contest=contest).delete()
    for rank, (entrant_key, data) in enumerate(ordered, start=1):
        defaults = {
            "score": data["score"],
            "penalty": data["penalty"],
            "rank": rank,
            "last_submission_at": data["last_submission_at"],
        }
        if contest.is_team_based:
            ContestLeaderboard.objects.create(contest=contest, team_id=entrant_key, **defaults)
        else:
            ContestLeaderboard.objects.create(contest=contest, participant_id=entrant_key, **defaults)
            contest.participants.filter(id=entrant_key).update(final_score=data["score"], penalty=data["penalty"], rank=rank)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"contest_{contest.id}_leaderboard",
        {
            "type": "leaderboard.message",
            "contest_id": contest.id,
        },
    )
    return ordered


def register_contest_activity(contest, user):
    log_user_activity(user, "contest", f"Joined {contest.title}", {"contest_id": contest.id})

