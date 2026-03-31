from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView, UpdateView
from django_ratelimit.decorators import ratelimit
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from .forms import OTPRegistrationForm, ProfileSetupForm, SignInForm
from .models import EmailOTP
from .services import (
    cleanup_expired_email_otps,
    clear_pending_registration,
    generate_email_otp,
    get_otp_attempts,
    get_otp_expiry_seconds,
    get_otp_max_attempts,
    get_pending_registration,
    increment_otp_attempts,
    latest_email_otp,
    normalize_email,
    reset_otp_attempts,
    seconds_until_otp_resend_allowed,
    store_pending_registration,
)
from .tasks import dispatch_user_sync, sync_user_all_platforms

User = get_user_model()


@method_decorator(never_cache, name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "users/login.html"
    authentication_form = SignInForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        return redirect(self.get_success_url())


@method_decorator(never_cache, name="dispatch")
class LogoutView(auth_views.LogoutView):
    http_method_names = ["post", "options"]
    next_page = "dashboard:landing"

    def post(self, request, *args, **kwargs):
        auth_logout(request)
        return redirect(self.request.POST.get("next", self.next_page))


class RegisterView(TemplateView):
    template_name = "users/register.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = OTPRegistrationForm()
        context["otp_expiry_minutes"] = max(1, get_otp_expiry_seconds() // 60)
        return context


class ProfileSetupView(UpdateView):
    form_class = ProfileSetupForm
    template_name = "users/profile_setup.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("users:login")
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        user = form.save()
        if user.has_connected_profiles:
            try:
                sync_user_all_platforms.delay(user.id)
            except (OperationalError, RedisError, OSError):
                dispatch_user_sync(user.id, force_sync=True)
            messages.success(self.request, "Profile saved. Your coding profiles are being synced.")
        else:
            messages.success(self.request, "Profile saved successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("profiles:detail", kwargs={"username": self.request.user.username})


@require_GET
def check_username(request):
    username = (request.GET.get("username") or "").strip()
    if not username:
        return JsonResponse({"available": False, "message": "Enter a username to check availability."}, status=400)

    username_field = User._meta.get_field("username").formfield()
    try:
        username = username_field.clean(username)
    except ValidationError as exc:
        return JsonResponse({"available": False, "message": exc.messages[0]}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"available": False, "message": "This username is already taken."})
    return JsonResponse({"available": True, "message": "This username is available."})


@require_POST
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def send_otp(request):
    cleanup_expired_email_otps()
    form = OTPRegistrationForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "ok": False,
                "message": "Please correct the highlighted fields before requesting an OTP.",
                "errors": {field: [str(message) for message in messages_list] for field, messages_list in form.errors.items()},
            },
            status=400,
        )

    email = form.cleaned_data["email"]
    retry_after = seconds_until_otp_resend_allowed(email)
    if retry_after:
        return JsonResponse(
            {
                "ok": False,
                "message": f"Please wait {retry_after} seconds before requesting another OTP.",
                "retry_after": retry_after,
            },
            status=429,
        )

    otp = generate_email_otp()
    EmailOTP.objects.filter(email=email).delete()
    otp_record = EmailOTP.objects.create(email=email, otp=otp)
    store_pending_registration(request, form.cleaned_data)
    reset_otp_attempts(email)

    try:
        send_mail(
            subject="Your CodeArena verification code",
            message=(
                f"Your CodeArena OTP is {otp}.\n\n"
                f"It expires in {max(1, get_otp_expiry_seconds() // 60)} minutes."
            ),
            from_email=None,
            recipient_list=[email],
        )
    except Exception:
        otp_record.delete()
        clear_pending_registration(request)
        return JsonResponse(
            {
                "ok": False,
                "message": "We could not send the OTP email right now. Please check your email configuration and try again.",
            },
            status=500,
        )

    return JsonResponse(
        {
            "ok": True,
            "message": "OTP sent successfully. Check your inbox and enter the 6-digit code below.",
            "expires_in": get_otp_expiry_seconds(),
            "retry_after": seconds_until_otp_resend_allowed(email),
        }
    )


@require_POST
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def verify_otp(request):
    cleanup_expired_email_otps()
    email = normalize_email(request.POST.get("email", ""))
    otp = (request.POST.get("otp") or "").strip()

    if not email or not otp:
        return JsonResponse({"ok": False, "message": "Email and OTP are required."}, status=400)
    if not otp.isdigit() or len(otp) != 6:
        return JsonResponse({"ok": False, "message": "Enter a valid 6-digit OTP."}, status=400)

    if get_otp_attempts(email) >= get_otp_max_attempts():
        EmailOTP.objects.filter(email=email).delete()
        clear_pending_registration(request)
        return JsonResponse(
            {
                "ok": False,
                "message": "Too many incorrect OTP attempts. Please request a new OTP.",
            },
            status=429,
        )

    pending_registration = get_pending_registration(request, email=email)
    if not pending_registration:
        return JsonResponse(
            {
                "ok": False,
                "message": "Your signup session expired or does not match this email. Please send a new OTP.",
            },
            status=400,
        )

    otp_record = latest_email_otp(email)
    if not otp_record:
        clear_pending_registration(request)
        return JsonResponse({"ok": False, "message": "No active OTP was found for this email. Please request a new one."}, status=400)

    if otp_record.is_expired():
        EmailOTP.objects.filter(email=email).delete()
        clear_pending_registration(request)
        return JsonResponse({"ok": False, "message": "This OTP has expired. Please request a new one."}, status=400)

    if otp_record.otp != otp:
        attempts = increment_otp_attempts(email)
        if attempts >= get_otp_max_attempts():
            EmailOTP.objects.filter(email=email).delete()
            clear_pending_registration(request)
            return JsonResponse(
                {
                    "ok": False,
                    "message": "Too many incorrect OTP attempts. Please request a new OTP.",
                },
                status=429,
            )
        return JsonResponse(
            {
                "ok": False,
                "message": f"Incorrect OTP. You have {get_otp_max_attempts() - attempts} attempt(s) remaining.",
            },
            status=400,
        )

    try:
        with transaction.atomic():
            if User.objects.filter(email__iexact=email).exists():
                EmailOTP.objects.filter(email=email).delete()
                clear_pending_registration(request)
                return JsonResponse({"ok": False, "message": "An account with this email already exists."}, status=400)
            if User.objects.filter(username__iexact=pending_registration["username"]).exists():
                EmailOTP.objects.filter(email=email).delete()
                clear_pending_registration(request)
                return JsonResponse({"ok": False, "message": "This username is no longer available. Please start again."}, status=400)

            user = User(username=pending_registration["username"], email=email)
            user.password = pending_registration["password_hash"]
            user.save()
    except IntegrityError:
        return JsonResponse({"ok": False, "message": "We could not complete registration. Please try again."}, status=400)

    EmailOTP.objects.filter(email=email).delete()
    clear_pending_registration(request)
    reset_otp_attempts(email)
    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Account verified successfully. Complete your profile to finish setup.")
    return JsonResponse({"ok": True, "redirect_url": reverse("profile-setup")})
