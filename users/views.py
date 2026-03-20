from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView

from .forms import SignInForm, SignUpForm
from .models import User


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


class RegisterView(CreateView):
    form_class = SignUpForm
    template_name = "users/register.html"
    success_url = "/dashboard/"

    def form_valid(self, form):
        response = super().form_valid(form)
        auth_login(self.request, self.object)
        messages.success(self.request, "Account created successfully. Welcome to CodeArena!")
        return redirect(self.success_url)

