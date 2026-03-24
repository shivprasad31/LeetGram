import json
import random

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from friends.models import Friendship
from groups.models import GroupMembership
from notifications.services import create_notification
from profiles.models import ProfileStatistics
from profiles.services import log_user_activity
from problems.models import Problem

from .execution import execute_python_code
from .models import Challenge, ChallengeEvent, ChallengeResult, ChallengeSubmission


def eligible_opponents_for(user):
    friendships = Friendship.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related("user_one", "user_two")
    candidates = {}
    for friendship in friendships:
        friend = friendship.user_two if friendship.user_one_id == user.id else friendship.user_one
        candidates[friend.id] = friend
    for membership in GroupMembership.objects.select_related("user").filter(group__memberships__user=user).exclude(user=user):
        candidates[membership.user_id] = membership.user
    return sorted(candidates.values(), key=lambda entry: entry.username.lower())


def user_groups_for(user):
    return (
        GroupMembership.objects.filter(user=user)
        .select_related("group")
        .order_by("group__name")
    )


def challenge_queryset_for(user):
    return (
        Challenge.objects.filter(Q(challenger=user) | Q(opponent=user))
        .select_related("challenger", "opponent", "problem", "group", "result", "result__winner", "result__loser")
        .prefetch_related("submissions__user", "events__user")
        .distinct()
    )


def _are_friends(user, other_user):
    ordered = sorted([user.id, other_user.id])
    return Friendship.objects.filter(user_one_id=ordered[0], user_two_id=ordered[1]).exists()


def _validate_can_challenge(challenger, opponent, group=None):
    if challenger == opponent:
        raise ValidationError("You cannot challenge yourself.")
    if group:
        shared_group = GroupMembership.objects.filter(group=group, user__in=[challenger, opponent]).values("user_id").distinct().count() == 2
        if not shared_group:
            raise ValidationError("Both players must belong to the selected group.")
        return
    if _are_friends(challenger, opponent):
        return
    if GroupMembership.objects.filter(user=challenger, group__memberships__user=opponent).exists():
        return
    raise ValidationError("Challenges are limited to friends or shared group members.")


def _normalize_test_cases(test_cases):
    if isinstance(test_cases, str):
        if not test_cases.strip():
            return []
        try:
            test_cases = json.loads(test_cases)
        except json.JSONDecodeError as exc:
            raise ValidationError("Test cases must be valid JSON.") from exc

    normalized = []
    for index, item in enumerate(test_cases or [], start=1):
        if not isinstance(item, dict):
            raise ValidationError(f"Test case {index} must be an object with input and output keys.")
        input_value = item.get("input", "")
        output_value = item.get("output", "")
        normalized.append(
            {
                "input": "" if input_value is None else str(input_value),
                "output": "" if output_value is None else str(output_value),
                "is_public": bool(item.get("is_public", index <= 2)),
            }
        )
    return normalized


def _public_cases_from(test_cases):
    return [{"input": item["input"], "output": item["output"]} for item in test_cases if item.get("is_public")]


def _problem_pool_for(challenger, opponent):
    common = (
        Problem.objects.filter(platform_problems__solvers__user=challenger)
        .filter(platform_problems__solvers__user=opponent)
        .distinct()
    )
    if common.exists():
        return common
    return Problem.objects.filter(platform_problems__solvers__user__in=[challenger, opponent]).distinct()


def _build_problem_snapshot(problem):
    statement = (problem.statement or "").strip()
    return {
        "title_snapshot": problem.canonical_name,
        "statement_snapshot": statement,
        "constraints_snapshot": "Implement solve(raw_input) and return the final answer as a string.",
    }


@transaction.atomic
def create_challenge(challenger, opponent, group=None, time_limit_minutes=30, test_cases=None):
    _validate_can_challenge(challenger, opponent, group=group)
    normalized_cases = _normalize_test_cases(test_cases)
    if not normalized_cases:
        raise ValidationError("Add at least one fixed test case for the coding battle.")

    pool = list(_problem_pool_for(challenger, opponent)[:100])
    if not pool:
        raise ValidationError("No solved problems are available yet between these users.")

    problem = random.choice(pool)
    snapshot = _build_problem_snapshot(problem)
    challenge = Challenge.objects.create(
        challenger=challenger,
        opponent=opponent,
        group=group,
        problem=problem,
        status=Challenge.STATUS_PENDING,
        test_cases=normalized_cases,
        public_test_cases=_public_cases_from(normalized_cases),
        **snapshot,
    )

    create_notification(
        opponent,
        "New coding battle",
        f"{challenger.username} challenged you to solve {problem.canonical_name}.",
        category="challenge",
        actor_user=challenger,
        action_url="/challenges/",
    )
    log_user_activity(challenger, "challenge", f"Challenged {opponent.username}", {"challenge_id": challenge.id})
    return challenge


@transaction.atomic
def accept_challenge(challenge, user):
    if challenge.opponent_id != user.id:
        raise PermissionDenied("Only the challenged user can accept this challenge.")
    if challenge.status != Challenge.STATUS_PENDING:
        raise ValidationError("This challenge can no longer be accepted.")

    challenge.status = Challenge.STATUS_ACCEPTED
    challenge.accepted_at = timezone.now()
    challenge.save(update_fields=["status", "accepted_at"])
    create_notification(
        challenge.challenger,
        "Challenge accepted",
        f"{user.username} accepted your coding battle.",
        category="challenge",
        actor_user=user,
        action_url=f"/challenges/{challenge.id}/room/",
    )
    return challenge


@transaction.atomic
def reject_challenge(challenge, user):
    if challenge.opponent_id != user.id:
        raise PermissionDenied("Only the challenged user can reject this challenge.")
    if challenge.status != Challenge.STATUS_PENDING:
        raise ValidationError("This challenge can no longer be rejected.")
    challenge.status = Challenge.STATUS_REJECTED
    challenge.end_time = timezone.now()
    challenge.save(update_fields=["status", "end_time"])
    return challenge


@transaction.atomic
def start_challenge(challenge, user):
    if user.id not in {challenge.challenger_id, challenge.opponent_id}:
        raise PermissionDenied("You are not part of this challenge.")
    if challenge.status not in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE}:
        raise ValidationError("This challenge cannot be started yet.")

    field_name = "challenger_joined_at" if user.id == challenge.challenger_id else "opponent_joined_at"
    if getattr(challenge, field_name) is None:
        setattr(challenge, field_name, timezone.now())

    update_fields = [field_name]
    if challenge.challenger_joined_at and challenge.opponent_joined_at and challenge.start_time is None:
        challenge.status = Challenge.STATUS_ACTIVE
        challenge.start_time = timezone.now()
        update_fields.extend(["status", "start_time"])

    challenge.save(update_fields=update_fields)
    return challenge


def _ensure_active_participant(challenge, user):
    if user.id not in {challenge.challenger_id, challenge.opponent_id}:
        raise PermissionDenied("You are not part of this challenge.")
    if challenge.status != Challenge.STATUS_ACTIVE:
        raise ValidationError("This challenge is not active yet.")
    if hasattr(challenge, "result"):
        raise ValidationError("This challenge has already finished.")


@transaction.atomic
def submit_challenge_code(challenge, user, code, language=Challenge.LANGUAGE_PYTHON):
    _ensure_active_participant(challenge, user)
    if language != Challenge.LANGUAGE_PYTHON:
        raise ValidationError("Only Python submissions are supported right now.")

    execution = execute_python_code(code, challenge.test_cases)
    elapsed = 0
    if challenge.start_time:
        elapsed = max(0, int((timezone.now() - challenge.start_time).total_seconds()))

    submission = ChallengeSubmission.objects.create(
        challenge=challenge,
        user=user,
        code=code,
        language=language,
        verdict=execution["verdict"],
        execution_time=execution["execution_time"],
        is_correct=execution["is_correct"],
        time_taken_seconds=elapsed,
        output=execution.get("output", ""),
        error_output=execution.get("error_output", ""),
    )

    if submission.is_correct:
        _finalize_challenge(challenge, submission)

    return submission


@transaction.atomic
def log_challenge_event(challenge, user, event_type, metadata=None):
    if user.id not in {challenge.challenger_id, challenge.opponent_id}:
        raise PermissionDenied("You are not part of this challenge.")
    return ChallengeEvent.objects.create(
        challenge=challenge,
        user=user,
        event_type=event_type,
        metadata=metadata or {},
    )


def _update_profile_stats(winner, loser):
    winner_stats, _ = ProfileStatistics.objects.get_or_create(user=winner)
    loser_stats, _ = ProfileStatistics.objects.get_or_create(user=loser)
    winner_stats.total_challenges = F("total_challenges") + 1
    winner_stats.challenge_wins = F("challenge_wins") + 1
    loser_stats.total_challenges = F("total_challenges") + 1
    winner_stats.save(update_fields=["total_challenges", "challenge_wins"])
    loser_stats.save(update_fields=["total_challenges"])


def _update_group_stats(challenge, winner, loser):
    if not challenge.group_id:
        return
    GroupMembership.objects.filter(group=challenge.group, user=winner).update(
        total_challenges=F("total_challenges") + 1,
        challenge_wins=F("challenge_wins") + 1,
    )
    GroupMembership.objects.filter(group=challenge.group, user=loser).update(
        total_challenges=F("total_challenges") + 1,
    )


def _finalize_challenge(challenge, winning_submission):
    if hasattr(challenge, "result"):
        return challenge.result

    winner = winning_submission.user
    loser = challenge.opponent if winner.id == challenge.challenger_id else challenge.challenger
    challenge.status = Challenge.STATUS_FINISHED
    challenge.end_time = timezone.now()
    challenge.winner = winner
    challenge.save(update_fields=["status", "end_time", "winner"])

    result = ChallengeResult.objects.create(
        challenge=challenge,
        winner=winner,
        loser=loser,
        winning_submission=winning_submission,
        time_taken=winning_submission.time_taken_seconds,
    )
    _update_profile_stats(winner, loser)
    _update_group_stats(challenge, winner, loser)
    create_notification(
        winner,
        "Battle won",
        f"You beat {loser.username} in a coding battle.",
        category="challenge",
        actor_user=winner,
        action_url=f"/challenges/{challenge.id}/room/",
    )
    create_notification(
        loser,
        "Battle finished",
        f"{winner.username} won the coding battle.",
        category="challenge",
        actor_user=winner,
        action_url=f"/challenges/{challenge.id}/room/",
    )
    log_user_activity(winner, "challenge", f"Won a challenge against {loser.username}", {"challenge_id": challenge.id})
    log_user_activity(loser, "challenge", f"Finished a challenge against {winner.username}", {"challenge_id": challenge.id})
    return result


def build_challenge_payload(challenge, current_user=None):
    latest_submissions = []
    for submission in challenge.submissions.select_related("user").order_by("-submitted_at")[:6]:
        latest_submissions.append(
            {
                "id": submission.id,
                "user_id": submission.user_id,
                "username": submission.user.username,
                "verdict": submission.verdict,
                "execution_time": submission.execution_time,
                "is_correct": submission.is_correct,
                "time_taken_seconds": submission.time_taken_seconds,
                "submitted_at": submission.submitted_at,
            }
        )

    result_payload = None
    if hasattr(challenge, "result"):
        result_payload = {
            "winner_id": challenge.result.winner_id,
            "winner_name": challenge.result.winner.username if challenge.result.winner else "",
            "loser_name": challenge.result.loser.username if challenge.result.loser else "",
            "time_taken": challenge.result.time_taken,
            "created_at": challenge.result.created_at,
        }

    latest_submission = None
    if current_user and getattr(current_user, "is_authenticated", False):
        latest_submission = (
            challenge.submissions.filter(user=current_user)
            .order_by("-submitted_at")
            .values("id", "verdict", "execution_time", "output", "error_output", "is_correct", "time_taken_seconds", "submitted_at")
            .first()
        )

    return {
        "id": challenge.id,
        "status": challenge.status,
        "challenger_id": challenge.challenger_id,
        "challenger_name": challenge.challenger.username,
        "opponent_id": challenge.opponent_id,
        "opponent_name": challenge.opponent.username,
        "group_name": challenge.group.name if challenge.group else "",
        "problem_id": challenge.problem_id,
        "problem_title": challenge.title_snapshot or (challenge.problem.canonical_name if challenge.problem else ""),
        "statement": challenge.statement_snapshot,
        "constraints": challenge.constraints_snapshot,
        "language": challenge.allowed_language,
        "created_at": challenge.created_at,
        "accepted_at": challenge.accepted_at,
        "start_time": challenge.start_time,
        "end_time": challenge.end_time,
        "challenger_joined_at": challenge.challenger_joined_at,
        "opponent_joined_at": challenge.opponent_joined_at,
        "public_test_cases": challenge.public_test_cases,
        "latest_submissions": latest_submissions,
        "latest_submission": latest_submission,
        "result": result_payload,
    }
