from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from codearena.context_processors import product_context

from .models import FriendRequest

User = get_user_model()


class FriendsPageViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="owner@example.com",
            username="OwnerUser",
            password="testpass123",
        )
        self.mixed_case_friend = User.objects.create_user(
            email="friend@example.com",
            username="MiXeDCoder",
            password="testpass123",
            bio="Enjoys graphs and dp",
        )
        self.client.force_login(self.user)

    def test_search_matches_username_case_insensitively(self):
        response = self.client.get(reverse("friends:index"), {"q": "mixedcoder"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MiXeDCoder")
        self.assertTrue(response.context["has_search_results"])
        self.assertTrue(response.context["discoverable_students"][0]["username_exact_match"])

    def test_search_shows_no_user_found_state(self):
        response = self.client.get(reverse("friends:index"), {"q": "does-not-exist"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No user found")
        self.assertFalse(response.context["has_search_results"])

    def test_product_context_exposes_pending_friend_request_count(self):
        sender = User.objects.create_user(
            email="sender@example.com",
            username="SenderUser",
            password="testpass123",
        )
        FriendRequest.objects.create(sender=sender, receiver=self.user, status="pending")
        request = self.factory.get("/")
        request.user = self.user

        context = product_context(request)

        self.assertEqual(context["pending_friend_requests_count"], 1)