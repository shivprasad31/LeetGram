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
from problems.models import Problem, TestCase as ProblemTestCase

from .execution import available_language_options, evaluate_code
from .models import Challenge, ChallengeEvent, ChallengeResult, ChallengeSubmission
from .realtime import broadcast_challenge_update


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
    return GroupMembership.objects.filter(user=user).select_related("group").order_by("group__name")


def challenge_queryset_for(user):
    return (
        Challenge.objects.filter(Q(challenger=user) | Q(opponent=user))
        .select_related(
            "challenger",
            "opponent",
            "problem",
            "difficulty",
            "group",
            "winner",
            "disqualified_user",
            "result",
            "result__winner",
            "result__loser",
            "result__winning_submission",
        )
        .prefetch_related("submissions__user", "events__user", "problem__test_cases")
        .distinct()
    )


def _save_challenge(challenge, *, update_fields):
    challenge.full_clean(validate_unique=False)
    challenge.save(update_fields=update_fields)
    return challenge


def _are_friends(user, other_user):
    ordered = sorted([user.id, other_user.id])
    return Friendship.objects.filter(user_one_id=ordered[0], user_two_id=ordered[1]).exists()


def _validate_can_challenge(challenger, opponent, group=None):
    if challenger == opponent:
        raise ValidationError("You cannot challenge yourself.")
    if group:
        shared_group = (
            GroupMembership.objects.filter(group=group, user__in=[challenger, opponent]).values("user_id").distinct().count() == 2
        )
        if not shared_group:
            raise ValidationError("Both players must belong to the selected group.")
    elif not _are_friends(challenger, opponent) and not GroupMembership.objects.filter(
        user=challenger,
        group__memberships__user=opponent,
    ).exists():
        raise ValidationError("Challenges are limited to friends or shared group members.")

    active_statuses = [Challenge.STATUS_PENDING, Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE]
    pair_conflict = Challenge.objects.filter(status__in=active_statuses).filter(
        Q(challenger=challenger, opponent=opponent) | Q(challenger=opponent, opponent=challenger)
    )
    if pair_conflict.exists():
        raise ValidationError("There is already an open challenge between these users.")


def _problem_pool_for(challenger, opponent):
    shared = (
        Problem.objects.filter(platform_problems__solvers__user=challenger)
        .filter(platform_problems__solvers__user=opponent)
        .filter(test_cases__isnull=False)
        .distinct()
    )
    if shared.exists():
        return shared
    return Problem.objects.filter(platform_problems__solvers__user__in=[challenger, opponent]).filter(test_cases__isnull=False).distinct()


def _problem_test_cases(problem, *, include_hidden=True):
    if not problem:
        return []
    queryset = problem.test_cases.all()
    if not include_hidden:
        queryset = queryset.filter(is_sample=True)
    return list(queryset)


def _serialize_problem_test_cases(test_cases):
    return [
        {
            "input": test_case.input_data,
            "output": test_case.expected_output,
            "is_sample": test_case.is_sample,
        }
        for test_case in test_cases
    ]


def _ensure_problem_is_runnable(problem):
    if not problem:
        raise ValidationError("This challenge does not have a problem assigned.")
    if not problem.test_cases.exists():
        raise ValidationError("This problem does not have any stored test cases yet.")
    return problem


def _build_problem_snapshot(problem):
    return {
        "title_snapshot": problem.title,
        "statement_snapshot": (problem.description or "").strip(),
        "constraints_snapshot": (problem.constraints or "").strip(),
    }


def _role_for(challenge, user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    if user.id == challenge.challenger_id:
        return "challenger"
    if user.id == challenge.opponent_id:
        return "opponent"
    return ""


def _participant_fields(challenge, user):
    role = _role_for(challenge, user)
    if role == "challenger":
        return {
            "role": role,
            "joined_at": "challenger_joined_at",
            "camera_active": "challenger_camera_active",
            "camera_snapshot": "challenger_camera_snapshot",
            "camera_updated_at": "challenger_camera_updated_at",
        }
    if role == "opponent":
        return {
            "role": role,
            "joined_at": "opponent_joined_at",
            "camera_active": "opponent_camera_active",
            "camera_snapshot": "opponent_camera_snapshot",
            "camera_updated_at": "opponent_camera_updated_at",
        }
    raise PermissionDenied("You are not part of this challenge.")


def _other_participant(challenge, user):
    if user.id == challenge.challenger_id:
        return challenge.opponent
    if user.id == challenge.opponent_id:
        return challenge.challenger
    raise PermissionDenied("You are not part of this challenge.")


def _seconds_since_start(challenge):
    if not challenge.start_time:
        return 0
    return max(0, int((timezone.now() - challenge.start_time).total_seconds()))


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


def _notify_battle_resolution(challenge, winner, loser, *, finish_reason, detail):
    create_notification(
        winner,
        "Battle won",
        detail,
        category="challenge",
        actor_user=winner,
        action_url=f"/challenges/{challenge.id}/room/",
    )

    loser_message = f"{winner.username} won the coding battle."
    if finish_reason == Challenge.FINISH_REASON_DISQUALIFIED:
        loser_message = f"You were disqualified. {winner.username} wins the coding battle."
    elif finish_reason == Challenge.FINISH_REASON_FORFEITED:
        loser_message = f"You forfeited the coding battle. {winner.username} wins."

    create_notification(
        loser,
        "Battle finished",
        loser_message,
        category="challenge",
        actor_user=winner,
        action_url=f"/challenges/{challenge.id}/room/",
    )


@transaction.atomic
def create_challenge(challenger, opponent, group=None, time_limit_minutes=30):
    _validate_can_challenge(challenger, opponent, group=group)

    pool = list(_problem_pool_for(challenger, opponent)[:100])
    if not pool:
        raise ValidationError("No solved problems with stored test cases are available yet between these users.")

    problem = random.choice(pool)
    _ensure_problem_is_runnable(problem)
    snapshot = _build_problem_snapshot(problem)
    challenge = Challenge.objects.create(
        challenger=challenger,
        opponent=opponent,
        group=group,
        problem=problem,
        difficulty=problem.difficulty,
        time_limit_minutes=time_limit_minutes,
        status=Challenge.STATUS_PENDING,
        **snapshot,
    )
    challenge.full_clean(validate_unique=False)

    create_notification(
        opponent,
        "New coding battle",
        f"{challenger.username} challenged you to solve {problem.title}.",
        category="challenge",
        actor_user=challenger,
        action_url="/challenges/",
    )
    log_user_activity(challenger, "challenge", f"Challenged {opponent.username}", {"challenge_id": challenge.id})
    broadcast_challenge_update(challenge)
    return challenge


@transaction.atomic
def accept_challenge(challenge, user):
    if challenge.opponent_id != user.id:
        raise PermissionDenied("Only the challenged user can accept this challenge.")
    if challenge.status != Challenge.STATUS_PENDING:
        raise ValidationError("This challenge can no longer be accepted.")

    challenge.status = Challenge.STATUS_ACCEPTED
    challenge.accepted_at = timezone.now()
    challenge.finish_reason = ""
    challenge.end_time = None
    challenge.disqualified_user = None
    challenge.winner = None
    challenge.challenger_joined_at = None
    challenge.opponent_joined_at = None
    challenge.start_time = None
    challenge.challenger_camera_active = False
    challenge.opponent_camera_active = False
    challenge.challenger_camera_snapshot = ""
    challenge.opponent_camera_snapshot = ""
    challenge.challenger_camera_updated_at = None
    challenge.opponent_camera_updated_at = None
    _save_challenge(
        challenge,
        update_fields=[
            "status",
            "accepted_at",
            "finish_reason",
            "end_time",
            "disqualified_user",
            "winner",
            "challenger_joined_at",
            "opponent_joined_at",
            "start_time",
            "challenger_camera_active",
            "opponent_camera_active",
            "challenger_camera_snapshot",
            "opponent_camera_snapshot",
            "challenger_camera_updated_at",
            "opponent_camera_updated_at",
        ],
    )
    create_notification(
        challenge.challenger,
        "Challenge accepted",
        f"{user.username} accepted your coding battle.",
        category="challenge",
        actor_user=user,
        action_url=f"/challenges/{challenge.id}/room/",
    )
    broadcast_challenge_update(challenge)
    return challenge


@transaction.atomic
def reject_challenge(challenge, user):
    if challenge.opponent_id != user.id:
        raise PermissionDenied("Only the challenged user can reject this challenge.")
    if challenge.status != Challenge.STATUS_PENDING:
        raise ValidationError("This challenge can no longer be rejected.")
    challenge.status = Challenge.STATUS_REJECTED
    challenge.finish_reason = Challenge.FINISH_REASON_REJECTED
    challenge.end_time = timezone.now()
    _save_challenge(challenge, update_fields=["status", "finish_reason", "end_time"])
    broadcast_challenge_update(challenge)
    return challenge


@transaction.atomic
def start_challenge(challenge, user):
    participant_fields = _participant_fields(challenge, user)
    if challenge.status not in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE}:
        raise ValidationError("This challenge cannot be started yet.")

    joined_field = participant_fields["joined_at"]
    update_fields = []
    if getattr(challenge, joined_field) is None:
        setattr(challenge, joined_field, timezone.now())
        update_fields.append(joined_field)

    if challenge.challenger_joined_at and challenge.opponent_joined_at and challenge.start_time is None:
        challenge.status = Challenge.STATUS_ACTIVE
        challenge.start_time = timezone.now()
        update_fields.extend(["status", "start_time"])

    if update_fields:
        _save_challenge(challenge, update_fields=update_fields)
        broadcast_challenge_update(challenge)
    return challenge


def _ensure_active_participant(challenge, user):
    _participant_fields(challenge, user)
    if challenge.status != Challenge.STATUS_ACTIVE:
        raise ValidationError("This challenge is not active yet.")
    if hasattr(challenge, "result"):
        raise ValidationError("This challenge has already finished.")
    _ensure_problem_is_runnable(challenge.problem)


def _best_correct_submission(challenge):
    return (
        challenge.submissions.filter(is_correct=True)
        .select_related("user")
        .order_by("time_taken_seconds", "execution_time", "submitted_at", "id")
        .first()
    )


@transaction.atomic
def _finish_battle(challenge, *, winner, loser, finish_reason, winning_submission=None, violating_user=None):
    if hasattr(challenge, "result"):
        return challenge.result

    challenge.status = Challenge.STATUS_FINISHED
    challenge.end_time = timezone.now()
    challenge.winner = winner
    challenge.finish_reason = finish_reason
    challenge.disqualified_user = violating_user
    _save_challenge(
        challenge,
        update_fields=["status", "end_time", "winner", "finish_reason", "disqualified_user"],
    )

    result = ChallengeResult.objects.create(
        challenge=challenge,
        winner=winner,
        loser=loser,
        winning_submission=winning_submission,
        time_taken=winning_submission.time_taken_seconds if winning_submission else _seconds_since_start(challenge),
    )
    _update_profile_stats(winner, loser)
    _update_group_stats(challenge, winner, loser)

    detail = f"You beat {loser.username} in a coding battle."
    if finish_reason == Challenge.FINISH_REASON_DISQUALIFIED:
        detail = f"{loser.username} was disqualified. You win the coding battle."
    elif finish_reason == Challenge.FINISH_REASON_FORFEITED:
        detail = f"{loser.username} forfeited the coding battle. You win."
    _notify_battle_resolution(challenge, winner, loser, finish_reason=finish_reason, detail=detail)
    log_user_activity(winner, "challenge", f"Won a challenge against {loser.username}", {"challenge_id": challenge.id})
    log_user_activity(loser, "challenge", f"Finished a challenge against {winner.username}", {"challenge_id": challenge.id})
    broadcast_challenge_update(challenge)
    return result


def problem_test_cases_for(problem, *, include_hidden=True):
    problem = _ensure_problem_is_runnable(problem)
    return _problem_test_cases(problem, include_hidden=include_hidden)


def run_code_for_problem(problem, code, language):
    return evaluate_code(code, language, problem_test_cases_for(problem, include_hidden=True))


@transaction.atomic
def submit_challenge_code(challenge, user, code, language=Challenge.LANGUAGE_PYTHON):
    _ensure_active_participant(challenge, user)
    execution = evaluate_code(code, language, problem_test_cases_for(challenge.problem, include_hidden=True))
    submission = ChallengeSubmission.objects.create(
        challenge=challenge,
        user=user,
        code=code,
        language=language,
        verdict=execution["verdict"],
        execution_time=execution["execution_time"],
        is_correct=execution["is_correct"],
        time_taken_seconds=_seconds_since_start(challenge),
        output=execution.get("output", ""),
        error_output=execution.get("error_output", ""),
    )
    submission.execution_details = execution

    if submission.is_correct and not hasattr(challenge, "result"):
        winner_submission = _best_correct_submission(challenge)
        if winner_submission:
            loser = challenge.opponent if winner_submission.user_id == challenge.challenger_id else challenge.challenger
            _finish_battle(
                challenge,
                winner=winner_submission.user,
                loser=loser,
                finish_reason=Challenge.FINISH_REASON_COMPLETED,
                winning_submission=winner_submission,
            )
    broadcast_challenge_update(challenge)
    return submission


@transaction.atomic
def forfeit_challenge(challenge, user):
    _participant_fields(challenge, user)
    if challenge.status not in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE}:
        raise ValidationError("Only accepted or active challenges can be forfeited.")
    if hasattr(challenge, "result"):
        raise ValidationError("This challenge is already finished.")

    opponent = _other_participant(challenge, user)
    return _finish_battle(
        challenge,
        winner=opponent,
        loser=user,
        finish_reason=Challenge.FINISH_REASON_FORFEITED,
        violating_user=user,
    )


@transaction.atomic
def update_challenge_presence(challenge, user, *, camera_active, snapshot_data=""):
    participant_fields = _participant_fields(challenge, user)
    if challenge.status in {Challenge.STATUS_REJECTED, Challenge.STATUS_FINISHED}:
        return challenge

    update_fields = [participant_fields["camera_active"], participant_fields["camera_updated_at"]]
    setattr(challenge, participant_fields["camera_active"], bool(camera_active))
    setattr(challenge, participant_fields["camera_updated_at"], timezone.now())
    if snapshot_data:
        setattr(challenge, participant_fields["camera_snapshot"], snapshot_data)
        update_fields.append(participant_fields["camera_snapshot"])
    elif not camera_active:
        setattr(challenge, participant_fields["camera_snapshot"], "")
        update_fields.append(participant_fields["camera_snapshot"])

    _save_challenge(challenge, update_fields=update_fields)

    if camera_active:
        ChallengeEvent.objects.create(
            challenge=challenge,
            user=user,
            event_type=ChallengeEvent.EVENT_CAMERA_HEARTBEAT,
            metadata={"camera_active": True},
        )
        return challenge

    ChallengeEvent.objects.create(
        challenge=challenge,
        user=user,
        event_type=ChallengeEvent.EVENT_CAMERA_BLOCKED,
        metadata={"camera_active": False},
    )
    if challenge.status in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE} and not hasattr(challenge, "result"):
        opponent = _other_participant(challenge, user)
        _finish_battle(
            challenge,
            winner=opponent,
            loser=user,
            finish_reason=Challenge.FINISH_REASON_DISQUALIFIED,
            violating_user=user,
        )
    return challenge


@transaction.atomic
def log_challenge_event(challenge, user, event_type, metadata=None):
    _participant_fields(challenge, user)
    event = ChallengeEvent.objects.create(
        challenge=challenge,
        user=user,
        event_type=event_type,
        metadata=metadata or {},
    )
    if event_type in {ChallengeEvent.EVENT_TAB_SWITCH, ChallengeEvent.EVENT_WINDOW_BLUR}:
        broadcast_challenge_update(challenge)
    return event


def _problem_payload(challenge):
    if not challenge.can_view_problem:
        return {"title": "", "description": "", "constraints": "", "examples": [], "sample_count": 0, "hidden_count": 0}

    if challenge.problem_id:
        sample_cases = _problem_test_cases(challenge.problem, include_hidden=False)
        serialized_samples = _serialize_problem_test_cases(sample_cases)
        all_cases = _problem_test_cases(challenge.problem, include_hidden=True)
        examples = [{"input": item["input"], "output": item["output"]} for item in serialized_samples]
        return {
            "title": challenge.problem.title,
            "description": challenge.problem.description,
            "constraints": challenge.problem.constraints,
            "examples": examples,
            "sample_count": len(examples),
            "hidden_count": max(0, len(all_cases) - len(examples)),
        }

    return {
        "title": challenge.title_snapshot,
        "description": challenge.statement_snapshot,
        "constraints": challenge.constraints_snapshot,
        "examples": [],
        "sample_count": 0,
        "hidden_count": 0,
    }


def _room_message(challenge, current_user):
    if challenge.status == Challenge.STATUS_PENDING:
        if current_user and current_user.id == challenge.opponent_id:
            return "Accept or reject the challenge to unlock the battle room."
        return f"Waiting for {challenge.opponent.username} to accept the challenge."
    if challenge.status == Challenge.STATUS_ACCEPTED:
        waiting_for = []
        if not challenge.challenger_joined_at:
            waiting_for.append(challenge.challenger.username)
        if not challenge.opponent_joined_at:
            waiting_for.append(challenge.opponent.username)
        if waiting_for:
            return f"Waiting for {', '.join(waiting_for)} to join the room."
        return "Both players are connected. Starting the countdown."
    if challenge.status == Challenge.STATUS_ACTIVE:
        return "Battle live. Run code inside the judge sandbox, review the case results, then submit."
    if challenge.status == Challenge.STATUS_FINISHED:
        if challenge.finish_reason == Challenge.FINISH_REASON_DISQUALIFIED and challenge.disqualified_user:
            return f"{challenge.disqualified_user.username} was disqualified. The battle is over."
        if challenge.finish_reason == Challenge.FINISH_REASON_FORFEITED and challenge.disqualified_user:
            return f"{challenge.disqualified_user.username} forfeited the battle."
        return "Battle finished."
    if challenge.status == Challenge.STATUS_REJECTED:
        return "This challenge was rejected."
    return ""


def build_challenge_payload(challenge, current_user=None):
    viewer_role = _role_for(challenge, current_user)
    latest_submissions = []
    for submission in challenge.submissions.select_related("user").order_by("-submitted_at")[:8]:
        latest_submissions.append(
            {
                "id": submission.id,
                "user_id": submission.user_id,
                "username": submission.user.username,
                "language": submission.language,
                "verdict": submission.verdict,
                "execution_time": submission.execution_time,
                "is_correct": submission.is_correct,
                "time_taken_seconds": submission.time_taken_seconds,
                "submitted_at": submission.submitted_at,
            }
        )

    latest_submission = None
    if current_user and getattr(current_user, "is_authenticated", False):
        latest_submission = (
            challenge.submissions.filter(user=current_user)
            .order_by("-submitted_at")
            .values(
                "id",
                "language",
                "verdict",
                "execution_time",
                "output",
                "error_output",
                "is_correct",
                "time_taken_seconds",
                "submitted_at",
            )
            .first()
        )

    result_payload = None
    if hasattr(challenge, "result"):
        result_payload = {
            "winner_id": challenge.result.winner_id,
            "winner_name": challenge.result.winner.username if challenge.result.winner else "",
            "loser_id": challenge.result.loser_id,
            "loser_name": challenge.result.loser.username if challenge.result.loser else "",
            "time_taken": challenge.result.time_taken,
            "created_at": challenge.result.created_at,
            "finish_reason": challenge.finish_reason,
            "violating_user_id": challenge.disqualified_user_id,
            "violating_user_name": challenge.disqualified_user.username if challenge.disqualified_user else "",
        }

    viewer_camera_active = False
    viewer_camera_snapshot = ""
    viewer_camera_updated_at = None
    opponent_camera_active = False
    opponent_camera_snapshot = ""
    opponent_camera_updated_at = None
    if viewer_role == "challenger":
        viewer_camera_active = challenge.challenger_camera_active
        viewer_camera_snapshot = challenge.challenger_camera_snapshot
        viewer_camera_updated_at = challenge.challenger_camera_updated_at
        opponent_camera_active = challenge.opponent_camera_active
        opponent_camera_snapshot = challenge.opponent_camera_snapshot
        opponent_camera_updated_at = challenge.opponent_camera_updated_at
    elif viewer_role == "opponent":
        viewer_camera_active = challenge.opponent_camera_active
        viewer_camera_snapshot = challenge.opponent_camera_snapshot
        viewer_camera_updated_at = challenge.opponent_camera_updated_at
        opponent_camera_active = challenge.challenger_camera_active
        opponent_camera_snapshot = challenge.challenger_camera_snapshot
        opponent_camera_updated_at = challenge.challenger_camera_updated_at

    return {
        "id": challenge.id,
        "status": challenge.status,
        "room_state": "waiting_room" if challenge.status == Challenge.STATUS_ACCEPTED else challenge.status,
        "challenge_title": challenge.title_snapshot or "Coding Battle",
        "challenger_id": challenge.challenger_id,
        "challenger_name": challenge.challenger.username,
        "opponent_id": challenge.opponent_id,
        "opponent_name": challenge.opponent.username,
        "viewer_role": viewer_role,
        "can_accept": bool(current_user and current_user.id == challenge.opponent_id and challenge.status == Challenge.STATUS_PENDING),
        "can_reject": bool(current_user and current_user.id == challenge.opponent_id and challenge.status == Challenge.STATUS_PENDING),
        "can_join": challenge.status in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE},
        "can_view_problem": challenge.can_view_problem,
        "can_submit": challenge.status == Challenge.STATUS_ACTIVE,
        "can_run_code": challenge.status in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE},
        "can_forfeit": challenge.status in {Challenge.STATUS_ACCEPTED, Challenge.STATUS_ACTIVE},
        "group_name": challenge.group.name if challenge.group else "",
        "problem_id": challenge.problem_id,
        "problem": _problem_payload(challenge),
        "language": challenge.allowed_language,
        "language_options": available_language_options(),
        "time_limit_minutes": challenge.time_limit_minutes,
        "created_at": challenge.created_at,
        "accepted_at": challenge.accepted_at,
        "start_time": challenge.start_time,
        "end_time": challenge.end_time,
        "challenger_joined_at": challenge.challenger_joined_at,
        "opponent_joined_at": challenge.opponent_joined_at,
        "waiting_message": _room_message(challenge, current_user),
        "countdown_seconds": 3,
        "latest_submissions": latest_submissions,
        "latest_submission": latest_submission,
        "result": result_payload,
        "monitoring": {
            "current_user_camera_active": viewer_camera_active,
            "current_user_snapshot": viewer_camera_snapshot,
            "current_user_updated_at": viewer_camera_updated_at,
            "opponent_camera_active": opponent_camera_active,
            "opponent_snapshot": opponent_camera_snapshot,
            "opponent_updated_at": opponent_camera_updated_at,
            "violating_user_id": challenge.disqualified_user_id,
            "violating_user_name": challenge.disqualified_user.username if challenge.disqualified_user else "",
        },
    }
