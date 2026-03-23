from django.db import transaction
from django.utils import timezone

from notifications.services import create_notification
from problems.models import PlatformProblem, Problem, UserSolvedProblem
from problems.services import ensure_problem_difficulty, get_standard_difficulty
from revision.services import enqueue_problem_for_revision

from .models import IntegrationStatus
from .services import CodeforcesService, GFGService, HackerRankService, LeetCodeService, PlatformServiceError
from .utils import normalize_problem_title


class SyncService:
    PLATFORM_FIELD_MAP = {
        "codeforces": "codeforces_username",
        "leetcode": "leetcode_username",
        "gfg": "gfg_username",
        "hackerrank": "hackerrank_username",
    }

    PLATFORM_SERVICES = {
        "codeforces": CodeforcesService,
        "leetcode": LeetCodeService,
        "gfg": GFGService,
        "hackerrank": HackerRankService,
    }

    @classmethod
    def get_connected_platforms(cls, user):
        connected = []
        for platform, field_name in cls.PLATFORM_FIELD_MAP.items():
            username = (getattr(user, field_name, "") or "").strip()
            if username:
                connected.append((platform, username))
        return connected

    @classmethod
    def sync_user_all_platforms(cls, user):
        results = []
        total_new = 0
        for platform, _ in cls.get_connected_platforms(user):
            result = cls.sync_user_platform(user, platform)
            total_new += result.get("created_count", 0)
            results.append(result)

        user.last_synced_at = timezone.now()
        user.save(update_fields=["last_synced_at"])
        if total_new:
            create_notification(
                user,
                "Problem sync complete",
                f"{total_new} new solved problem{'s' if total_new != 1 else ''} synced across your connected platforms.",
                category="integration",
                action_url=f"/profiles/{user.username}/",
            )
        return {"user_id": user.id, "results": results, "created_count": total_new}

    @classmethod
    def sync_user_platform(cls, user, platform, submissions_limit=100):
        if platform not in cls.PLATFORM_SERVICES:
            raise ValueError(f"Unsupported platform: {platform}")

        username = (getattr(user, cls.PLATFORM_FIELD_MAP[platform], "") or "").strip()
        status, _ = IntegrationStatus.objects.get_or_create(user=user, platform=platform)
        if not username:
            return {
                "platform": platform,
                "status": "skipped",
                "created_count": 0,
            }

        service = cls.PLATFORM_SERVICES[platform]()
        try:
            if not service.validate_username(username):
                raise PlatformServiceError(f"{platform.title()} profile '{username}' was not found.")

            submissions = service.fetch_solved_submissions(username=username, since=status.last_synced, limit=submissions_limit)
            created_count = 0
            latest_seen = status.last_synced

            with transaction.atomic():
                for submission in sorted(submissions, key=lambda item: item.get("solved_at") or timezone.now()):
                    normalized_title = normalize_problem_title(submission.get("title"))
                    if not normalized_title:
                        continue

                    difficulty = get_standard_difficulty(submission.get("difficulty"))
                    problem, _ = Problem.objects.get_or_create(
                        canonical_name=normalized_title,
                        defaults={"difficulty": difficulty},
                    )
                    ensure_problem_difficulty(problem, submission.get("difficulty"))
                    platform_problem, pp_created = PlatformProblem.objects.get_or_create(
                        platform=platform,
                        platform_id=submission["platform_id"],
                        defaults={
                            "title": normalized_title,
                            "url": submission.get("url", ""),
                            "problem": problem,
                        },
                    )
                    changed_fields = []
                    if platform_problem.problem_id != problem.id:
                        platform_problem.problem = problem
                        changed_fields.append("problem")
                    if normalized_title and platform_problem.title != normalized_title:
                        platform_problem.title = normalized_title
                        changed_fields.append("title")
                    submission_url = submission.get("url", "")
                    if submission_url and platform_problem.url != submission_url:
                        platform_problem.url = submission_url
                        changed_fields.append("url")
                    if changed_fields and not pp_created:
                        platform_problem.save(update_fields=changed_fields)

                    _, solved_created = UserSolvedProblem.objects.get_or_create(
                        user=user,
                        platform_problem=platform_problem,
                        defaults={"solved_at": submission.get("solved_at") or timezone.now()},
                    )
                    enqueue_problem_for_revision(
                        user,
                        problem,
                        next_review_at=(submission.get("solved_at") or timezone.now()) + timezone.timedelta(days=1),
                    )
                    if solved_created:
                        created_count += 1
                    if submission.get("solved_at") and (latest_seen is None or submission["solved_at"] > latest_seen):
                        latest_seen = submission["solved_at"]

                status.last_synced = latest_seen or timezone.now()
                status.status = "success"
                status.error_message = ""
                status.save(update_fields=["last_synced", "status", "error_message"])

            return {
                "platform": platform,
                "status": "success",
                "created_count": created_count,
                "last_synced": status.last_synced.isoformat() if status.last_synced else None,
            }
        except PlatformServiceError as exc:
            status.status = "failed"
            status.error_message = str(exc)[:1000]
            status.save(update_fields=["status", "error_message"])
            raise
        except Exception as exc:
            status.status = "failed"
            status.error_message = str(exc)[:1000]
            status.save(update_fields=["status", "error_message"])
            raise
