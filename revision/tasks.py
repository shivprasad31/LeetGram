from django.utils import timezone

from celery import shared_task

from notifications.services import create_notification
from .models import RevisionItem


@shared_task
def send_revision_reminders():
    due_items = RevisionItem.objects.select_related("revision_list__user", "problem").filter(next_review_at__lte=timezone.now(), is_mastered=False)
    for item in due_items:
        create_notification(
            item.revision_list.user,
            "Revision reminder",
            f"{item.problem.canonical_name} is ready for another review session.",
            category="revision",
            action_url="/revision/",
        )
    return due_items.count()

