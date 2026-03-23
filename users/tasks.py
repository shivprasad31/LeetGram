from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from integrations.sync import SyncService

User = get_user_model()


def _connected_users_queryset():
    return User.objects.filter(
        Q(codeforces_username__isnull=False)
        | Q(leetcode_username__isnull=False)
        | Q(gfg_username__isnull=False)
        | Q(hackerrank_username__isnull=False)
    ).exclude(
        Q(codeforces_username="")
        & Q(leetcode_username="")
        & Q(gfg_username="")
        & Q(hackerrank_username="")
    )


def _sync_user_all_platforms_now(user_id):
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return {"status": "missing-user", "user_id": user_id}
    return SyncService.sync_user_all_platforms(user)


def dispatch_user_sync(user_id, *, force_sync=False):
    if force_sync:
        return {"mode": "sync", "result": _sync_user_all_platforms_now(user_id)}

    try:
        sync_user_all_platforms.delay(user_id)
        return {"mode": "queued"}
    except (OperationalError, RedisError, OSError):
        result = _sync_user_all_platforms_now(user_id)
        return {"mode": "sync", "result": result}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def sync_user_all_platforms(self, user_id):
    return _sync_user_all_platforms_now(user_id)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def sync_recent_submissions(self):
    queued_user_ids = []
    for user_id in _connected_users_queryset().values_list("id", flat=True):
        dispatch_user_sync(user_id)
        queued_user_ids.append(user_id)

    return {"status": "queued", "count": len(queued_user_ids), "user_ids": queued_user_ids}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def sync_connected_user_profiles(self):
    queued_user_ids = []
    for user_id in _connected_users_queryset().values_list("id", flat=True):
        dispatch_user_sync(user_id)
        queued_user_ids.append(user_id)

    return {"status": "queued", "count": len(queued_user_ids), "user_ids": queued_user_ids}
