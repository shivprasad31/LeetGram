from collections import OrderedDict
from copy import deepcopy
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

from integrations.models import IntegrationStatus

INTEGRATION_PLATFORMS = OrderedDict(
    [
        (
            "codeforces_username",
            {
                "label": "Codeforces",
                "icon": "bi-trophy",
                "placeholder": "Enter your Codeforces handle",
                "help_text": "Letters, numbers, underscores, hyphens, and dots only.",
            },
        ),
        (
            "leetcode_username",
            {
                "label": "LeetCode",
                "icon": "bi-code-slash",
                "placeholder": "Enter your LeetCode username",
                "help_text": "Letters, numbers, underscores, hyphens, and dots only.",
            },
        ),
        (
            "gfg_username",
            {
                "label": "GeeksforGeeks",
                "icon": "bi-journal-code",
                "placeholder": "Enter your GeeksforGeeks username",
                "help_text": "Letters, numbers, underscores, hyphens, and dots only.",
            },
        ),
        (
            "hackerrank_username",
            {
                "label": "HackerRank",
                "icon": "bi-terminal-dash",
                "placeholder": "Enter your HackerRank username",
                "help_text": "Letters, numbers, underscores, hyphens, and dots only.",
            },
        ),
    ]
)

HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{2,80}$")


def normalize_integration_username(value):
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def validate_integration_username(value, platform_label):
    normalized = normalize_integration_username(value)
    if normalized is None:
        return None
    if not HANDLE_PATTERN.fullmatch(normalized):
        raise ValidationError(
            f"{platform_label} usernames can only contain letters, numbers, dots, hyphens, and underscores."
        )
    return normalized


class IntegrationFieldsMixin:
    integration_fields = tuple(INTEGRATION_PLATFORMS.keys())

    def clean(self):
        cleaned_data = super().clean()
        seen_values = {}

        for field_name, meta in INTEGRATION_PLATFORMS.items():
            value = cleaned_data.get(field_name)
            normalized = validate_integration_username(value, meta["label"])
            cleaned_data[field_name] = normalized
            if not normalized:
                continue

            duplicate_key = normalized.casefold()
            if duplicate_key in seen_values:
                self.add_error(
                    field_name,
                    f"This username is already used for {seen_values[duplicate_key]}. Use a distinct handle per platform.",
                )
            else:
                seen_values[duplicate_key] = meta["label"]

        return cleaned_data


def build_integration_rows(user):
    status_map = {
        item.platform: item
        for item in IntegrationStatus.objects.filter(user=user)
    }
    rows = []
    for field_name, meta in INTEGRATION_PLATFORMS.items():
        username = getattr(user, field_name, None)
        platform = field_name.replace("_username", "")
        sync_status = status_map.get(platform)
        if not username:
            status = "Not connected"
        elif sync_status and sync_status.status == "failed":
            status = "Sync failed"
        elif sync_status and sync_status.last_synced:
            status = "Connected"
        else:
            status = "Pending sync"
        rows.append(
            {
                "field": field_name,
                "platform": meta["label"],
                "icon": meta["icon"],
                "placeholder": meta["placeholder"],
                "username": username,
                "status": status,
                "is_connected": bool(username) and status != "Sync failed",
                "sync_failed": status == "Sync failed",
                "error_message": sync_status.error_message if sync_status and sync_status.status == "failed" else "",
            }
        )
    return rows


def get_integration_payload(user):
    return {
        "profiles": build_integration_rows(user),
        "last_synced_at": timezone.localtime(user.last_synced_at).isoformat() if user.last_synced_at else None,
        "has_connected_profiles": user.has_connected_profiles,
    }


def update_user_integrations(user, cleaned_data):
    updated_fields = []

    for field_name in INTEGRATION_PLATFORMS:
        new_value = cleaned_data.get(field_name)
        if getattr(user, field_name) != new_value:
            setattr(user, field_name, new_value)
            updated_fields.append(field_name)

    if updated_fields:
        user.save(update_fields=updated_fields)

    return updated_fields


def integration_field_widgets(base_class):
    widgets = {}
    for field_name, meta in INTEGRATION_PLATFORMS.items():
        widgets[field_name] = base_class(
            attrs={
                "placeholder": meta["placeholder"],
                "autocomplete": "off",
            }
        )
    return widgets


def integration_field_help_texts():
    return {field_name: deepcopy(meta["help_text"]) for field_name, meta in INTEGRATION_PLATFORMS.items()}