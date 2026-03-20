import random

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notifications.services import create_notification
from profiles.services import log_user_activity
from problems.models import Problem

from .models import Challenge, ChallengeProblem, ChallengeResult


@transaction.atomic
def create_challenge(sender, receiver, difficulty=None, time_limit_minutes=90):
    shared_pool = Problem.objects.filter(solvers__user=sender).filter(solvers__user=receiver).distinct()
    if difficulty:
        shared_pool = shared_pool.filter(difficulty=difficulty)
    shared_pool = list(shared_pool[:50])
    if len(shared_pool) < 3:
        raise ValidationError("Need at least three shared solved problems to create this challenge.")

    challenge = Challenge.objects.create(
        sender=sender,
        receiver=receiver,
        difficulty=difficulty,
        time_limit_minutes=time_limit_minutes,
    )
    for position, problem in enumerate(random.sample(shared_pool, 3), start=1):
        ChallengeProblem.objects.create(challenge=challenge, problem=problem, position=position)

    create_notification(receiver, "New challenge", f"{sender.username} challenged you to a coding duel.", category="challenge", actor_user=sender, action_url="/challenges/")
    log_user_activity(sender, "challenge", f"Challenged {receiver.username}", {"challenge_id": challenge.id})
    return challenge


@transaction.atomic
def accept_challenge(challenge, user):
    if challenge.receiver != user:
        raise ValidationError("Only the challenged user can accept this challenge.")
    challenge.status = "accepted"
    challenge.accepted_at = timezone.now()
    challenge.save(update_fields=["status", "accepted_at"])
    create_notification(challenge.sender, "Challenge accepted", f"{user.username} accepted your challenge.", category="challenge", actor_user=user, action_url=f"/challenges/?challenge={challenge.id}")
    return challenge


@transaction.atomic
def start_challenge(challenge):
    challenge.status = "running"
    challenge.started_at = timezone.now()
    challenge.save(update_fields=["status", "started_at"])
    return challenge


@transaction.atomic
def submit_challenge_result(challenge, user, score, solved_count, completion_time_seconds):
    result, _ = ChallengeResult.objects.update_or_create(
        challenge=challenge,
        user=user,
        defaults={
            "score": score,
            "solved_count": solved_count,
            "completion_time_seconds": completion_time_seconds,
        },
    )
    results = list(challenge.results.select_related("user"))
    if len(results) == 2:
        results.sort(key=lambda entry: (-entry.score, entry.completion_time_seconds, entry.user.username))
        winner = results[0].user if (results[0].score, -results[0].completion_time_seconds) != (results[1].score, -results[1].completion_time_seconds) else None
        challenge.status = "finished"
        challenge.finished_at = timezone.now()
        challenge.winner = winner
        challenge.save(update_fields=["status", "finished_at", "winner"])
        if winner:
            create_notification(winner, "Challenge won", f"You won the challenge against {challenge.receiver.username if winner == challenge.sender else challenge.sender.username}.", category="challenge", level="success", action_url="/challenges/")
            log_user_activity(winner, "challenge", "Won a challenge", {"challenge_id": challenge.id})
    return result

