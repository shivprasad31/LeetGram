from django.db.models.signals import post_save
from django.dispatch import receiver

from dashboard.models import UserPreference
from profiles.models import ProfileStatistics
from revision.models import RevisionList
from users.models import User


@receiver(post_save, sender=User)
def bootstrap_user_records(sender, instance, created, **kwargs):
    if not created:
        return
    ProfileStatistics.objects.get_or_create(user=instance)
    UserPreference.objects.get_or_create(user=instance)
    RevisionList.objects.get_or_create(
        user=instance,
        is_default=True,
        defaults={
            "title": "Core Revision Queue",
            "description": "Automatically curated revision list for spaced repetition.",
        },
    )

