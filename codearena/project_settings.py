import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WINDOWS_LOCAL_REDIS = "redis://127.0.0.1:6379"
DEFAULT_REDIS_BASE = WINDOWS_LOCAL_REDIS if os.name == "nt" else "redis://redis:6379"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-leetwise-dev-key")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",") if host]
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if origin
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "channels",
    "django_celery_beat",
    "users.apps.UsersConfig",
    "profiles.apps.ProfilesConfig",
    "friends.apps.FriendsConfig",
    "groups.apps.GroupsConfig",
    "problems.apps.ProblemsConfig",
    "challenges.apps.ChallengesConfig",
    "revision.apps.RevisionConfig",
    "ranking.apps.RankingConfig",
    "notifications.apps.NotificationsConfig",
    "dashboard.apps.DashboardConfig",
    "integrations.apps.IntegrationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "codearena.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "codearena.context_processors.theme_settings",
                "codearena.context_processors.product_context",
            ],
        },
    },
]

WSGI_APPLICATION = "codearena.wsgi.application"
ASGI_APPLICATION = "codearena.asgi.application"

if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "dashboard:landing"
LOGOUT_REDIRECT_URL = "dashboard:landing"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend" if os.getenv("EMAIL_HOST") else "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "LeetWise <noreply@leetwise.dev>")
OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REDIS_URL = os.getenv("REDIS_URL", f"{DEFAULT_REDIS_BASE}/1")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 300,
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "leetwise-local-cache",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"{DEFAULT_REDIS_BASE}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"{DEFAULT_REDIS_BASE}/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_POOL = os.getenv("CELERY_WORKER_POOL", "solo" if os.name == "nt" else "prefork")
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "1" if os.name == "nt" else "4"))
CELERY_BEAT_SCHEDULE = {
    "sync-recent-submissions": {
        "task": "users.tasks.sync_recent_submissions",
        "schedule": timedelta(minutes=5),
    }
}

RATELIMIT_USE_CACHE = "default"

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CODEARENA_COLORS = {
    "primary": "#FF6B6B",
    "secondary": "#4ECDC4",
    "accent": "#FFE66D",
    "dark": "#1A1A1A",
    "light": "#F7F7F7",
}

CELERY_TASK_ALWAYS_EAGER = DEBUG and not REDIS_URL
CELERY_TASK_EAGER_PROPAGATES = True

# Problem Sync System Settings
SYNC_RATE_LIMIT = "10/m"  # 10 requests per minute per platform
SYNC_BATCH_SIZE = 50
SYNC_RETRY_LIMIT = 5
SYNC_DELAY_BETWEEN_CALLS = 1.0  # seconds

CHALLENGE_USE_DOCKER = os.getenv("CHALLENGE_USE_DOCKER", "True").lower() == "true"
CHALLENGE_DOCKER_IMAGE = os.getenv("CHALLENGE_DOCKER_IMAGE", "python:3.11-alpine")
CHALLENGE_DOCKER_PYTHON_IMAGE = os.getenv("CHALLENGE_DOCKER_PYTHON_IMAGE", CHALLENGE_DOCKER_IMAGE)
CHALLENGE_DOCKER_JAVA_IMAGE = os.getenv("CHALLENGE_DOCKER_JAVA_IMAGE", "eclipse-temurin:21-jdk-alpine")
CHALLENGE_DOCKER_MEMORY = os.getenv("CHALLENGE_DOCKER_MEMORY", "128m")
CHALLENGE_DOCKER_CPUS = os.getenv("CHALLENGE_DOCKER_CPUS", "0.50")
CHALLENGE_EXECUTION_TIMEOUT_SECONDS = int(os.getenv("CHALLENGE_EXECUTION_TIMEOUT_SECONDS", "5"))
CHALLENGE_MONACO_CDN = os.getenv(
    "CHALLENGE_MONACO_CDN",
    "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs",
)
