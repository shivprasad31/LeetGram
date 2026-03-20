from celery import shared_task

from .models import ExternalProfileConnection
from .services import sync_connection


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_external_profile(self, connection_id):
    connection = ExternalProfileConnection.objects.get(id=connection_id)
    try:
        sync_connection(connection)
    except Exception:
        connection.sync_status = "failed"
        connection.save(update_fields=["sync_status"])
        raise


@shared_task
def sync_all_external_profiles():
    for connection in ExternalProfileConnection.objects.filter(is_active=True):
        sync_external_profile.delay(connection.id)

