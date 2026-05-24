from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import User
from .tasks import sync_connected_user_profiles


class RegistrationTests(TestCase):
    # OTP flow removed; tests for OTP send/verify have been retired.

    def test_check_username_reports_existing_value(self):
        User.objects.create_user(
            email="existing@example.com",
            username="takenname",
            password="strong-pass-123",
        )

        response = self.client.get(reverse("check-username"), {"username": "takenname"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])

    def test_api_register_endpoint_creates_user(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "api@example.com",
                "username": "apiuser",
                "password": "strong-pass-123",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.filter(email="api@example.com").count(), 1)

    def test_profile_setup_saves_handles_and_dispatches_sync(self):
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="strong-pass-123",
        )
        self.client.force_login(user)

        with patch("users.views.sync_user_all_platforms.delay") as mocked_delay, patch(
            "users.forms.LeetCodeService.validate_username", return_value=True
        ), patch(
            "users.forms.CodeforcesService.validate_username", return_value=True
        ):
            response = self.client.post(
                reverse("profile-setup"),
                {
                    "bio": "I like graphs.",
                    "leetcode_username": "leet_user",
                    "codeforces_username": "cf-user",
                },
            )

        user.refresh_from_db()
        self.assertRedirects(response, reverse("profiles:detail", args=[user.username]))
        self.assertEqual(user.bio, "I like graphs.")
        self.assertEqual(user.leetcode_username, "leet_user")
        self.assertEqual(user.codeforces_username, "cf-user")
        mocked_delay.assert_called_once_with(user.id)


class AutomaticProfileSyncTests(TestCase):
    def test_periodic_sync_queues_only_users_with_connected_profiles(self):
        connected = User.objects.create_user(
            email="connected@example.com",
            username="connected-user",
            password="strong-pass-123",
            leetcode_username="leet_user",
        )
        User.objects.create_user(
            email="plain@example.com",
            username="plain-user",
            password="strong-pass-123",
        )

        with patch("users.tasks.sync_user_all_platforms.delay") as mocked_delay:
            result = sync_connected_user_profiles()

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["user_ids"], [connected.id])
        mocked_delay.assert_called_once_with(connected.id)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="logout@example.com",
            username="logoutuser",
            password="strong-pass-123",
        )

    def test_login_redirects_to_home(self):
        response = self.client.post(
            reverse("users:login"),
            {
                "username": "logout@example.com",
                "password": "strong-pass-123",
            },
        )
        self.assertRedirects(response, "/")


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
