import json
from datetime import UTC, datetime
from urllib.parse import urljoin

from django.utils import timezone
from django.utils.text import slugify


def coerce_submission_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)

    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=UTC)

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


def normalize_problem_title(title):
    return " ".join((title or "").split()).strip()


def build_problem_url(base_url, path):
    if not path:
        return ""
    return urljoin(base_url, path)


def slug_or_value(value):
    normalized = slugify(normalize_problem_title(value))
    return normalized or str(value)


def to_json_bytes(payload):
    return json.dumps(payload).encode("utf-8")