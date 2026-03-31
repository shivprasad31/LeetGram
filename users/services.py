import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.utils import timezone

from .models import EmailOTP, User


PENDING_REGISTRATION_SESSION_KEY = "pending_registration"


def normalize_email(email):
    return User.objects.normalize_email((email or "").strip()).lower()


def generate_email_otp():
    return f"{secrets.randbelow(900000) + 100000:06d}"


def get_otp_expiry_seconds():
    return getattr(settings, "OTP_EXPIRY_SECONDS", 300)


def get_otp_resend_cooldown_seconds():
    return getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)


def get_otp_max_attempts():
    return getattr(settings, "OTP_MAX_ATTEMPTS", 5)


def cleanup_expired_email_otps():
    cutoff = timezone.now() - timezone.timedelta(seconds=get_otp_expiry_seconds())
    EmailOTP.objects.filter(created_at__lt=cutoff).delete()


def latest_email_otp(email):
    return EmailOTP.objects.filter(email=email).order_by("-created_at").first()


def seconds_until_otp_resend_allowed(email):
    latest = latest_email_otp(email)
    if not latest:
        return 0
    next_allowed_at = latest.created_at + timezone.timedelta(seconds=get_otp_resend_cooldown_seconds())
    remaining = int((next_allowed_at - timezone.now()).total_seconds())
    return max(0, remaining)


def otp_attempt_cache_key(email):
    return f"signup_otp_attempts:{email}"


def get_otp_attempts(email):
    return int(cache.get(otp_attempt_cache_key(email), 0) or 0)


def reset_otp_attempts(email):
    cache.delete(otp_attempt_cache_key(email))


def increment_otp_attempts(email):
    key = otp_attempt_cache_key(email)
    attempts = get_otp_attempts(email) + 1
    cache.set(key, attempts, timeout=get_otp_expiry_seconds())
    return attempts


def store_pending_registration(request, cleaned_data):
    request.session[PENDING_REGISTRATION_SESSION_KEY] = {
        "username": cleaned_data["username"],
        "email": normalize_email(cleaned_data["email"]),
        "password_hash": make_password(cleaned_data["password1"]),
        "stored_at": timezone.now().isoformat(),
    }
    request.session.modified = True


def get_pending_registration(request, email=None):
    payload = request.session.get(PENDING_REGISTRATION_SESSION_KEY)
    if not payload:
        return None
    if email and payload.get("email") != normalize_email(email):
        return None
    return payload


def clear_pending_registration(request):
    if PENDING_REGISTRATION_SESSION_KEY in request.session:
        del request.session[PENDING_REGISTRATION_SESSION_KEY]
        request.session.modified = True
