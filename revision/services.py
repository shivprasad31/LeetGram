from decimal import Decimal

from django.utils import timezone

from .models import RevisionItem, RevisionList


def enqueue_problem_for_revision(user, problem, *, next_review_at=None):
    revision_list = user.revision_lists.filter(is_default=True).first() or user.revision_lists.first()
    if not revision_list:
        revision_list = RevisionList.objects.create(
            user=user,
            title="Core Revision Queue",
            description="Automatically curated revision list for spaced repetition.",
            is_default=True,
        )

    review_time = next_review_at or (timezone.now() + timezone.timedelta(days=1))
    revision_item, _ = RevisionItem.objects.get_or_create(
        revision_list=revision_list,
        problem=problem,
        defaults={"next_review_at": review_time},
    )
    return revision_item


def review_revision_item(item, quality):
    quality = max(0, min(int(quality), 5))
    ease_factor = Decimal(item.ease_factor)
    if quality < 3:
        item.repetitions = 0
        item.interval_days = 1
        ease_factor = max(Decimal("1.30"), ease_factor - Decimal("0.20"))
    else:
        item.repetitions += 1
        if item.repetitions == 1:
            item.interval_days = 1
        elif item.repetitions == 2:
            item.interval_days = 3
        else:
            item.interval_days = max(1, int(item.interval_days * float(ease_factor)))
        ease_factor = max(Decimal("1.30"), ease_factor + Decimal("0.10") - Decimal(5 - quality) * Decimal("0.02"))

    item.ease_factor = ease_factor.quantize(Decimal("0.01"))
    item.last_reviewed_at = timezone.now()
    item.next_review_at = item.last_reviewed_at + timezone.timedelta(days=item.interval_days)
    item.is_mastered = item.repetitions >= 5 and quality >= 4
    item.save()
    return item

