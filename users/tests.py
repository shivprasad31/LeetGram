from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import User


class RegistrationTests(TestCase):
    def setUp(self):
        self.email = "test@example.com"
        self.password = "strong-pass-123"
        self.username = "testuser"

    def test_registration_logs_in_immediately(self):
        response = self.client.post(reverse("users:register"), {
            "email": self.email,
            "username": self.username,
            "password": self.password,
            "password_confirm": self.password,
        })
        
        # Check if user was created and redirected to dashboard
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get(email=self.email)
        self.assertTrue(user.email_verified)
        self.assertRedirects(response, reverse("dashboard:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="logout@example.com",
            username="logoutuser",
            password="strong-pass-123",
        )

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(reverse("users:login"), {
            "username": "logout@example.com",
            "password": "strong-pass-123",
        })
        self.assertRedirects(response, "/dashboard/")


class LogoutFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="logout@example.com",
            username="logoutuser",
            password="strong-pass-123",
        )

    def test_logout_clears_authenticated_session_and_redirects_home(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:logout"), follow=True)

        self.assertRedirects(response, reverse("dashboard:landing"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Login")
        self.assertNotContains(response, "View Profile")
