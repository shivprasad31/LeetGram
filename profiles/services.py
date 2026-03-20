from profiles.models import UserActivity


def log_user_activity(user, activity_type, description, metadata=None):
    return UserActivity.objects.create(
        user=user,
        activity_type=activity_type,
        description=description,
        metadata=metadata or {},
    )

