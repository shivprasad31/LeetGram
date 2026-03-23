from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from integrations.models import IntegrationStatus
from users.models import User


class ProfileIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            username="profile-user",
            password="strong-pass-123",
        )

    def test_profile_edit_page_shows_connected_profiles_section(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profiles:edit", args=[self.user.username]))

        self.assertContains(response, "Connected Profiles")
        self.assertContains(response, "Sync Now")
        self.assertContains(response, "Codeforces")

    def test_connect_profiles_endpoint_updates_user_and_triggers_sync(self):
        self.client.force_login(self.user)

        with patch("profiles.views.dispatch_user_sync") as mocked_dispatch, patch(
            "integrations.services.LeetCodeService.validate_username", return_value=True
        ), patch(
            "integrations.services.CodeforcesService.validate_username", return_value=True
        ), patch(
            "integrations.services.GFGService.validate_username", return_value=True
        ), patch(
            "integrations.services.HackerRankService.validate_username", return_value=True
        ):
            response = self.client.post(
                reverse("connect-profiles"),
                {
                    "leetcode_username": "leet_user",
                    "codeforces_username": "cf-user",
                    "gfg_username": "gfg.user",
                    "hackerrank_username": "hr_user",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.leetcode_username, "leet_user")
        self.assertEqual(self.user.hackerrank_username, "hr_user")
        mocked_dispatch.assert_called_once_with(self.user.id)

    def test_sync_now_requires_connected_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("sync-now"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 400)

    def test_sync_now_returns_failed_status_for_invalid_platform_username(self):
        self.user.leetcode_username = "missing-user"
        self.user.save(update_fields=["leetcode_username"])
        self.client.force_login(self.user)

        with patch("integrations.services.LeetCodeService.validate_username", return_value=False):
            response = self.client.post(reverse("sync-now"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 400)
        self.assertIn("profile", response.json()["message"].lower())
        status = IntegrationStatus.objects.get(user=self.user, platform="leetcode")
        self.assertEqual(status.status, "failed")
