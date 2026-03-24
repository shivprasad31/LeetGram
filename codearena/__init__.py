try:
    from codearena.celery import app as celery_app
except ModuleNotFoundError:
    celery_app = None

__all__ = ("celery_app",)
