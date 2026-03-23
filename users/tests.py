from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import User
from .tasks import sync_connected_user_profiles


class RegistrationTests(TestCase):
    def test_registration_logs_in_immediately_and_schedules_sync_when_profiles_are_connected(self):
        with patch("users.views.sync_user_all_platforms.delay") as mocked_delay:
            response = self.client.post(
                reverse("users:register"),
                {
                    "email": "test@example.com",
                    "username": "testuser",
                    "password1": "strong-pass-123",
                    "password2": "strong-pass-123",
                    "bio": "I like graphs.",
                    "leetcode_username": "leet_user",
                    "codeforces_username": "cf-user",
                },
            )

        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get(email="test@example.com")
        self.assertRedirects(response, "/dashboard/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
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

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("users:login"),
            {
                "username": "logout@example.com",
                "password": "strong-pass-123",
            },
        )
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
