from django.test import RequestFactory, TestCase
from django.urls import reverse
import json

from codearena.context_processors import theme_settings
from users.models import User


class LandingPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="learner@example.com",
            username="learner",
            password="strong-pass-123",
        )

    def test_landing_page_shows_public_actions_for_anonymous_users(self):
        response = self.client.get(reverse("dashboard:landing"))

        self.assertContains(response, "Start Free")
        self.assertContains(response, "Login")
        self.assertNotContains(response, "View Profile")

    def test_landing_page_shows_member_actions_for_authenticated_users(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard:landing"))

        self.assertContains(response, "Open Dashboard")
        self.assertContains(response, "View Profile")
        self.assertNotContains(response, "Start Free")


class ThemeContextProcessorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="theme@example.com",
            username="themeuser",
            password="strong-pass-123",
        )

    def test_system_theme_preference_is_preserved(self):
        self.user.preference.theme_mode = "system"
        self.user.preference.save(update_fields=["theme_mode"])
        request = self.factory.get("/")
        request.user = self.user

        context = theme_settings(request)

        self.assertEqual(context["theme"], "system")
        self.assertEqual(context["theme_preference"], "system")

    def test_dark_theme_preference_is_returned_directly(self):
        self.user.preference.theme_mode = "dark"
        self.user.preference.save(update_fields=["theme_mode"])
        request = self.factory.get("/")
        request.user = self.user

        context = theme_settings(request)

        self.assertEqual(context["theme"], "dark")
        self.assertEqual(context["theme_preference"], "dark")


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="dashboard@example.com",
            username="dashboarduser",
            password="strong-pass-123",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_renders_successfully(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:dashboard"))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/dashboard.html")
        self.assertIn("chart_labels", response.context)
        self.assertIn("chart_values", response.context)
        
        # Verify JSON validity
        labels = json.loads(response.context["chart_labels"])
        values = json.loads(response.context["chart_values"])
        self.assertIsInstance(labels, list)
        self.assertIsInstance(values, list)
