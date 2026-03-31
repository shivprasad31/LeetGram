from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import EmailOTP, User
from .tasks import sync_connected_user_profiles


class RegistrationTests(TestCase):
    def test_send_otp_stores_code_and_sends_email(self):
        response = self.client.post(
            reverse("send-otp"),
            {
                "email": "test@example.com",
                "username": "testuser",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmailOTP.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verification code", mail.outbox[0].subject.lower())

    def test_verify_otp_creates_account_logs_user_in_and_redirects_to_profile_setup(self):
        self.client.post(
            reverse("send-otp"),
            {
                "email": "test@example.com",
                "username": "testuser",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
            },
        )
        otp = EmailOTP.objects.get(email="test@example.com").otp

        response = self.client.post(
            reverse("verify-otp"),
            {
                "email": "test@example.com",
                "otp": otp,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get(email="test@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(response.json()["redirect_url"], reverse("profile-setup"))

    def test_verify_otp_rejects_too_many_attempts(self):
        self.client.post(
            reverse("send-otp"),
            {
                "email": "test@example.com",
                "username": "testuser",
                "password1": "strong-pass-123",
                "password2": "strong-pass-123",
            },
        )

        for _ in range(5):
            response = self.client.post(
                reverse("verify-otp"),
                {
                    "email": "test@example.com",
                    "otp": "000000",
                },
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(EmailOTP.objects.count(), 0)

    def test_check_username_reports_existing_value(self):
        User.objects.create_user(
            email="existing@example.com",
            username="takenname",
            password="strong-pass-123",
        )

        response = self.client.get(reverse("check-username"), {"username": "takenname"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["available"])

    def test_api_register_endpoint_is_disabled_without_otp(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "api@example.com",
                "username": "apiuser",
                "password": "strong-pass-123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("otp", response.json()["detail"].lower())

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
