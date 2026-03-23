from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from profiles.services import sync_profile_statistics

from .models import UserSolvedProblem


@receiver(post_save, sender=UserSolvedProblem)
def update_profile_statistics_after_solve_save(sender, instance, **kwargs):
    sync_profile_statistics(instance.user)


@receiver(post_delete, sender=UserSolvedProblem)
def update_profile_statistics_after_solve_delete(sender, instance, **kwargs):
    sync_profile_statistics(instance.user)
