from django.test import TestCase
from django.urls import reverse

from users.models import User


class ProfileEditPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            username="profile-user",
            password="strong-pass-123",
        )

    def test_profile_edit_page_shows_extension_setup_card(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("profiles:edit", args=[self.user.username]))

        self.assertContains(response, "LeetCode Extension")
        self.assertContains(response, "Generate Token")
        self.assertContains(response, "extension-backend-url")
