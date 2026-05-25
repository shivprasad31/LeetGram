from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView, UpdateView
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from .forms import OTPRegistrationForm, ProfileSetupForm, SignInForm
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
        return context

    def post(self, request, *args, **kwargs):
        form = OTPRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password1"]
            user = User.objects.create_user(email=email, username=username, password=password)
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Account created successfully. Complete your profile to finish setup.")
            return redirect(reverse("profile-setup"))
        return render(request, self.template_name, {"form": form})


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
            except (OperationalError, RedisError, OSError, RuntimeError):
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



