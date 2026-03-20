from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse

from problems.models import Problem, UserSolvedProblem
from users.models import User

from .models import ExternalProfileConnection


class LeetCodeExtensionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="extension@example.com",
            username="extension-user",
            password="strong-pass-123",
        )
        self.connection = ExternalProfileConnection.objects.create(
            user=self.user,
            platform="leetcode",
            username="leetuser",
            profile_url="https://leetcode.com/leetuser/",
            is_active=True,
        )
        self.authenticated_client = APIClient()
        self.authenticated_client.force_authenticate(user=self.user)

    def accepted_payload(self):
        return {
            "submission_id": "123456789",
            "status_code": 10,
            "status_display": "Accepted",
            "timestamp": 1710000000,
            "runtime_ms": 52,
            "memory_kb": 18200,
            "lang": "python3",
            "question": {
                "question_id": "1",
                "frontend_question_id": "1",
                "title": "Two Sum",
                "title_slug": "two-sum",
                "difficulty": "Easy",
                "paid_only": False,
                "content": "<p>Given an array of integers...</p>",
                "ac_rate": "54.2",
                "topic_tags": [
                    {"name": "Array", "slug": "array"},
                    {"name": "Hash Table", "slug": "hash-table"},
                ],
            },
        }

    def test_issue_token_returns_ingest_endpoint(self):
        response = self.authenticated_client.post(reverse("integration-issue-token", args=[self.connection.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.api_token)
        self.assertEqual(response.data["api_token"], self.connection.api_token)
        self.assertIn("/api/integrations/leetcode/submissions/", response.data["endpoint"])

    def test_submission_ingest_creates_problem_and_solved_entry(self):
        self.connection.api_token = "extension-token"
        self.connection.save(update_fields=["api_token"])

        response = self.client.post(
            reverse("api-leetcode-submission"),
            data=self.accepted_payload(),
            format="json",
            HTTP_X_LEETGRAM_TOKEN="extension-token",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["created"])
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(UserSolvedProblem.objects.count(), 1)

        problem = Problem.objects.get()
        solved = UserSolvedProblem.objects.get()
        self.user.refresh_from_db()
        self.connection.refresh_from_db()

        self.assertEqual(problem.title, "Two Sum")
        self.assertEqual(problem.platform, "leetcode")
        self.assertEqual(problem.difficulty.slug, "easy")
        self.assertEqual(problem.tags.count(), 2)
        self.assertEqual(solved.submission_id, "123456789")
        self.assertEqual(solved.runtime_ms, 52)
        self.assertEqual(solved.memory_kb, 18200)
        self.assertEqual(self.user.solved_count, 1)
        self.assertEqual(self.user.leetcode_username, "leetuser")
        self.assertEqual(self.connection.remote_solved_count, 1)

    def test_duplicate_submission_updates_existing_entry_without_creating_duplicate(self):
        self.connection.api_token = "extension-token"
        self.connection.save(update_fields=["api_token"])
        payload = self.accepted_payload()

        first_response = self.client.post(
            reverse("api-leetcode-submission"),
            data=payload,
            format="json",
            HTTP_X_LEETGRAM_TOKEN="extension-token",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        payload["runtime_ms"] = 44
        payload["memory_kb"] = 17600
        second_response = self.client.post(
            reverse("api-leetcode-submission"),
            data=payload,
            format="json",
            HTTP_X_LEETGRAM_TOKEN="extension-token",
        )

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(UserSolvedProblem.objects.count(), 1)
        solved = UserSolvedProblem.objects.get()
        self.assertEqual(solved.runtime_ms, 44)
        self.assertEqual(solved.memory_kb, 17600)
