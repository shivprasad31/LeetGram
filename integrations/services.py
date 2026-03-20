import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify

from notifications.services import create_notification
from problems.models import Problem, ProblemDifficulty, ProblemTag, UserSolvedProblem
from profiles.models import ProfileStatistics
from profiles.services import log_user_activity

from .models import ExternalProfileConnection


@dataclass
class ProfileSnapshot:
    rating: int = 0
    solved_count: int = 0
    solved_problems: list = field(default_factory=list)


DIFFICULTY_MAP = {
    "easy": {"weight": 1, "color": "#4ECDC4"},
    "medium": {"weight": 2, "color": "#FFE66D"},
    "hard": {"weight": 3, "color": "#FF6B6B"},
}

LEETCODE_ACCEPTED_STATUS = 10
LEETCODE_POINTS = {
    "easy": 100,
    "medium": 200,
    "hard": 300,
}


class BaseProvider:
    timeout = 20.0

    def __init__(self, connection):
        self.connection = connection
        self.client = httpx.Client(timeout=self.timeout, follow_redirects=True)

    def fetch(self):
        raise NotImplementedError


class CodeforcesProvider(BaseProvider):
    def fetch(self):
        info_response = self.client.get("https://codeforces.com/api/user.info", params={"handles": self.connection.username})
        info_response.raise_for_status()
        info = info_response.json()["result"][0]

        status_response = self.client.get("https://codeforces.com/api/user.status", params={"handle": self.connection.username, "from": 1, "count": 200})
        status_response.raise_for_status()
        submissions = status_response.json()["result"]

        solved = {}
        for entry in submissions:
            if entry.get("verdict") != "OK":
                continue
            problem = entry.get("problem", {})
            external_id = f"{problem.get('contestId', 'cf')}-{problem.get('index', '')}"
            solved[external_id] = {
                "external_id": external_id,
                "title": problem.get("name", "Unknown Problem"),
                "url": f"https://codeforces.com/problemset/problem/{problem.get('contestId')}/{problem.get('index')}",
                "difficulty": self._map_rating(problem.get("rating")),
                "tags": problem.get("tags", []),
                "points": problem.get("rating") or 100,
                "platform": "codeforces",
                "solved_at": timezone.datetime.fromtimestamp(entry.get("creationTimeSeconds", 0), tz=ZoneInfo("UTC")),
                "submission_id": str(entry.get("id", "")),
            }

        return ProfileSnapshot(
            rating=info.get("rating", 0),
            solved_count=len(solved),
            solved_problems=list(solved.values()),
        )

    @staticmethod
    def _map_rating(rating):
        rating = rating or 0
        if rating <= 1200:
            return "easy"
        if rating <= 1700:
            return "medium"
        return "hard"


class LeetCodeProvider(BaseProvider):
    def fetch(self):
        headers = {"Referer": f"https://leetcode.com/{self.connection.username}/"}
        cookies = {"LEETCODE_SESSION": self.connection.session_cookie} if self.connection.session_cookie else None
        response = self.client.get("https://leetcode.com/api/problems/all/", headers=headers, cookies=cookies)
        response.raise_for_status()
        payload = response.json()

        solved = []
        for item in payload.get("stat_status_pairs", []):
            if item.get("status") != "ac":
                continue
            stat = item.get("stat", {})
            solved.append(
                {
                    "external_id": str(stat.get("question_id")),
                    "title": stat.get("question__title", "Unknown Problem"),
                    "url": f"https://leetcode.com/problems/{stat.get('question__title_slug', '')}/",
                    "difficulty": self._map_difficulty(item.get("difficulty", {}).get("level")),
                    "tags": [],
                    "points": item.get("paid_only", False) and 150 or 100,
                    "platform": "leetcode",
                    "solved_at": timezone.now(),
                    "submission_id": "",
                    "statement": "",
                    "acceptance_rate": Decimal("0"),
                    "is_premium": item.get("paid_only", False),
                }
            )

        return ProfileSnapshot(
            rating=0,
            solved_count=payload.get("num_solved") or len(solved),
            solved_problems=solved,
        )

    @staticmethod
    def _map_difficulty(level):
        return {1: "easy", 2: "medium", 3: "hard"}.get(level, "medium")


class GeeksForGeeksProvider(BaseProvider):
    def fetch(self):
        profile_url = f"https://auth.geeksforgeeks.org/user/{self.connection.username}/"
        response = self.client.get(profile_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        text = soup.get_text(" ", strip=True)
        match = re.search(r"(\d+)\s+Problems Solved", text)
        solved_count = int(match.group(1)) if match else 0
        problems = []
        for anchor in soup.select("a[href*='/problems/']")[:100]:
            title = anchor.get_text(strip=True)
            href = anchor.get("href", "")
            if not title:
                continue
            problems.append(
                {
                    "external_id": href.rstrip("/").split("/")[-1] or title.lower().replace(" ", "-"),
                    "title": title,
                    "url": href if href.startswith("http") else f"https://practice.geeksforgeeks.org{href}",
                    "difficulty": "medium",
                    "tags": ["practice"],
                    "points": 100,
                    "platform": "gfg",
                    "solved_at": timezone.now(),
                    "submission_id": "",
                    "statement": "",
                    "acceptance_rate": Decimal("0"),
                    "is_premium": False,
                }
            )
        unique = {entry["external_id"]: entry for entry in problems}
        return ProfileSnapshot(rating=0, solved_count=solved_count or len(unique), solved_problems=list(unique.values()))


def get_provider(connection):
    providers = {
        "codeforces": CodeforcesProvider,
        "leetcode": LeetCodeProvider,
        "gfg": GeeksForGeeksProvider,
    }
    return providers[connection.platform](connection)


def default_profile_url(platform, username):
    if platform == "leetcode":
        return f"https://leetcode.com/{username}/"
    if platform == "codeforces":
        return f"https://codeforces.com/profile/{username}"
    return f"https://auth.geeksforgeeks.org/user/{username}/"


def _build_difficulty_cache():
    cache = {}
    for level, meta in DIFFICULTY_MAP.items():
        cache[level], _ = ProblemDifficulty.objects.get_or_create(
            slug=level,
            defaults={"name": level.title(), "weight": meta["weight"], "color": meta["color"]},
        )
    return cache


def _normalize_acceptance_rate(value):
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _normalize_statement(content):
    if not content:
        return ""
    text = strip_tags(content)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_runtime_ms(value):
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"(\d+)", str(value))
    return int(match.group(1)) if match else None


def _normalize_memory_kb(value):
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"([\d.]+)\s*([KMG]?B)?", str(value), flags=re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "KB").upper()
    if unit == "GB":
        return int(amount * 1024 * 1024)
    if unit == "MB":
        return int(amount * 1024)
    return int(amount)


def _normalize_solved_at(value):
    if isinstance(value, timezone.datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value, timezone.get_current_timezone())
    if isinstance(value, (int, float)):
        return timezone.datetime.fromtimestamp(value, tz=ZoneInfo("UTC"))
    return timezone.now()


def _normalize_tags(tags):
    normalized = []
    for raw_tag in tags or []:
        if isinstance(raw_tag, dict):
            name = (raw_tag.get("name") or raw_tag.get("slug") or "").strip()
            slug = (raw_tag.get("slug") or slugify(name)).strip()
        else:
            name = str(raw_tag).strip()
            slug = slugify(name)
        if not name:
            continue
        normalized.append({"name": name.title(), "slug": slug or slugify(name)})
    return normalized


def _upsert_problem_from_item(item, difficulty_cache, tag_cache):
    difficulty = difficulty_cache.get(item["difficulty"], difficulty_cache["medium"])
    external_id = item.get("external_id") or None
    lookup = {"platform": item["platform"], "external_id": external_id} if external_id else {"platform": item["platform"], "title": item["title"]}
    problem, _ = Problem.objects.get_or_create(
        **lookup,
        defaults={
            "title": item["title"],
            "url": item.get("url", ""),
            "difficulty": difficulty,
            "points": item.get("points", 100),
            "source": item.get("source", item["platform"].title()),
            "statement": item.get("statement", ""),
            "acceptance_rate": item.get("acceptance_rate", Decimal("0")),
            "is_premium": item.get("is_premium", False),
        },
    )

    changed_fields = []
    updates = {
        "title": item["title"],
        "url": item.get("url", ""),
        "difficulty": difficulty,
        "points": item.get("points", 100),
        "source": item.get("source", item["platform"].title()),
        "acceptance_rate": item.get("acceptance_rate", Decimal("0")),
        "is_premium": item.get("is_premium", False),
    }
    if item.get("statement"):
        updates["statement"] = item["statement"]

    for field_name, value in updates.items():
        current = getattr(problem, field_name)
        current_value = current.id if field_name == "difficulty" else current
        next_value = value.id if field_name == "difficulty" else value
        if current_value != next_value:
            setattr(problem, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        problem.save(update_fields=changed_fields)

    for raw_tag in _normalize_tags(item.get("tags")):
        cache_key = raw_tag["slug"]
        tag = tag_cache.get(cache_key)
        if tag is None:
            tag, _ = ProblemTag.objects.get_or_create(
                slug=raw_tag["slug"],
                defaults={"name": raw_tag["name"], "color": "#4ECDC4"},
            )
            if tag.name != raw_tag["name"]:
                tag.name = raw_tag["name"]
                tag.save(update_fields=["name"])
            tag_cache[cache_key] = tag
        problem.tags.add(tag)

    return problem


def _upsert_solved_problem(user, problem, item):
    solved_problem, created = UserSolvedProblem.objects.get_or_create(
        user=user,
        problem=problem,
        defaults={
            "platform": item["platform"],
            "submission_id": item.get("submission_id", ""),
            "solved_at": item.get("solved_at") or timezone.now(),
            "runtime_ms": item.get("runtime_ms"),
            "memory_kb": item.get("memory_kb"),
            "notes": item.get("notes", ""),
        },
    )

    changed_fields = []
    mutable_updates = {
        "platform": item["platform"],
        "submission_id": item.get("submission_id", ""),
        "solved_at": item.get("solved_at") or solved_problem.solved_at,
        "runtime_ms": item.get("runtime_ms"),
        "memory_kb": item.get("memory_kb"),
    }
    if item.get("notes"):
        mutable_updates["notes"] = item.get("notes", "")

    for field_name, value in mutable_updates.items():
        if value is None:
            continue
        if getattr(solved_problem, field_name) != value:
            setattr(solved_problem, field_name, value)
            changed_fields.append(field_name)

    if changed_fields:
        solved_problem.save(update_fields=changed_fields)

    return solved_problem, created


def _refresh_user_statistics(user, rating=0, platform=None, platform_username=""):
    total_solved = user.solved_problems.count()
    stats, _ = ProfileStatistics.objects.get_or_create(user=user)
    stats.total_solved = total_solved
    stats.easy_solved = user.solved_problems.filter(problem__difficulty__slug="easy").count()
    stats.medium_solved = user.solved_problems.filter(problem__difficulty__slug="medium").count()
    stats.hard_solved = user.solved_problems.filter(problem__difficulty__slug="hard").count()
    stats.save()

    update_fields = ["solved_count", "last_synced_at"]
    user.solved_count = total_solved
    user.last_synced_at = timezone.now()
    if rating:
        user.rating = max(user.rating, rating)
        update_fields.append("rating")
    if platform and platform_username:
        setattr(user, f"{platform}_username", platform_username)
        update_fields.append(f"{platform}_username")
    user.save(update_fields=update_fields)
    return total_solved


@transaction.atomic
def sync_connection(connection):
    connection.sync_status = "running"
    connection.save(update_fields=["sync_status"])
    snapshot = get_provider(connection).fetch()

    difficulty_cache = _build_difficulty_cache()
    tag_cache = {}
    for item in snapshot.solved_problems:
        problem = _upsert_problem_from_item(item, difficulty_cache, tag_cache)
        _upsert_solved_problem(connection.user, problem, item)

    total_solved = _refresh_user_statistics(
        connection.user,
        rating=snapshot.rating,
        platform=connection.platform,
        platform_username=connection.username,
    )

    connection.profile_url = connection.profile_url or default_profile_url(connection.platform, connection.username)
    connection.last_synced_at = timezone.now()
    connection.sync_status = "success"
    connection.remote_rating = snapshot.rating
    connection.remote_solved_count = snapshot.solved_count or total_solved
    connection.save(update_fields=["profile_url", "last_synced_at", "sync_status", "remote_rating", "remote_solved_count"])

    create_notification(
        connection.user,
        f"{connection.platform.title()} sync completed",
        f"Imported {snapshot.solved_count} solved problems from {connection.platform.title()}.",
        category="system",
        level="success",
        action_url="/settings/",
    )
    log_user_activity(connection.user, "integration", f"Synced {connection.platform.title()} profile", {"platform": connection.platform, "solved_count": snapshot.solved_count})
    return snapshot


@transaction.atomic
def ingest_leetcode_submission(connection, payload):
    question = payload.get("question") or {}
    status_code = payload.get("status_code")
    status_display = (payload.get("status_display") or "").lower()
    is_accepted = status_code == LEETCODE_ACCEPTED_STATUS or status_display == "accepted"
    if not is_accepted:
        raise ValueError("Only accepted LeetCode submissions can be synced.")

    difficulty_value = str(question.get("difficulty") or "medium").strip().lower()
    difficulty = difficulty_value if difficulty_value in DIFFICULTY_MAP else LeetCodeProvider._map_difficulty(question.get("difficulty"))

    item = {
        "external_id": str(question.get("question_id") or question.get("frontend_question_id") or question.get("title_slug") or payload.get("submission_id")),
        "title": question.get("title") or "Unknown Problem",
        "url": f"https://leetcode.com/problems/{question.get('title_slug', '')}/",
        "difficulty": difficulty,
        "tags": question.get("topic_tags", []),
        "points": LEETCODE_POINTS.get(difficulty, 100),
        "platform": "leetcode",
        "solved_at": _normalize_solved_at(payload.get("timestamp")),
        "submission_id": str(payload.get("submission_id") or ""),
        "runtime_ms": _normalize_runtime_ms(payload.get("runtime_ms") or payload.get("runtime_display")),
        "memory_kb": _normalize_memory_kb(payload.get("memory_kb") or payload.get("memory_display")),
        "notes": payload.get("notes", ""),
        "statement": _normalize_statement(question.get("content")),
        "acceptance_rate": _normalize_acceptance_rate(question.get("ac_rate")),
        "is_premium": bool(question.get("paid_only", False)),
        "source": "LeetCode",
    }

    difficulty_cache = _build_difficulty_cache()
    tag_cache = {}
    problem = _upsert_problem_from_item(item, difficulty_cache, tag_cache)
    solved_problem, created = _upsert_solved_problem(connection.user, problem, item)
    total_solved = _refresh_user_statistics(connection.user, platform="leetcode", platform_username=connection.username)

    metadata = dict(connection.metadata or {})
    metadata.update(
        {
            "last_extension_submission_id": item["submission_id"],
            "last_extension_sync_at": timezone.now().isoformat(),
        }
    )
    connection.profile_url = connection.profile_url or default_profile_url("leetcode", connection.username)
    connection.last_synced_at = timezone.now()
    connection.sync_status = "success"
    connection.remote_solved_count = connection.user.solved_problems.filter(platform="leetcode").count()
    connection.metadata = metadata
    connection.save(update_fields=["profile_url", "last_synced_at", "sync_status", "remote_solved_count", "metadata"])

    if created:
        create_notification(
            connection.user,
            "LeetCode solve synced",
            f"Accepted submission for {problem.title} was added to your profile.",
            category="system",
            level="success",
            action_url=f"/problems/{problem.slug}/",
        )
        log_user_activity(
            connection.user,
            "integration",
            f"Synced accepted LeetCode submission for {problem.title}",
            {"platform": "leetcode", "submission_id": item["submission_id"]},
        )

    return {
        "created": created,
        "problem_title": problem.title,
        "problem_slug": problem.slug,
        "submission_id": solved_problem.submission_id,
        "total_solved": total_solved,
    }



