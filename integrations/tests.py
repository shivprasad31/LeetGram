from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from integrations.services import GFGService, HackerRankService
from integrations.sync import SyncService
from problems.models import UserSolvedProblem
from revision.models import RevisionItem

User = get_user_model()


class PlatformServiceParsingTests(TestCase):
    def test_gfg_service_parses_submission_payload(self):
        service = GFGService()
        payload = {
            "status": "success",
            "result": {
                "Medium": {
                    "705001": {
                        "slug": "find-nth-root-of-m5843",
                        "pname": "Find nth root of m",
                        "lang": "cpp",
                    }
                }
            },
        }

        with patch.object(service, "_get_json", return_value=payload):
            submissions = service.fetch_solved_submissions("demo-user")

        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0]["platform_id"], "705001")
        self.assertEqual(submissions[0]["title"], "Find nth root of m")
        self.assertIn("find-nth-root-of-m5843", submissions[0]["url"])

    def test_hackerrank_service_parses_recent_challenges_payload(self):
        service = HackerRankService()
        payload = {
            "models": [
                {
                    "name": "Java Singleton Pattern",
                    "ch_slug": "java-singleton",
                    "created_at": "2026-03-20T14:15:08.000+00:00",
                    "url": "/challenges/java-singleton",
                }
            ]
        }

        with patch.object(service, "_get_json", return_value=payload):
            submissions = service.fetch_solved_submissions("demo-user")

        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0]["platform_id"], "java-singleton")
        self.assertEqual(submissions[0]["title"], "Java Singleton Pattern")
        self.assertTrue(submissions[0]["url"].endswith("/challenges/java-singleton"))
        self.assertIsNotNone(submissions[0]["solved_at"])


class SyncRevisionIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sync@example.com",
            username="sync-user",
            password="strong-pass-123",
            hackerrank_username="sync-hacker",
        )

    def test_synced_problem_is_added_to_revision_queue(self):
        class FakeHackerRankService:
            def validate_username(self, username):
                return True

            def fetch_solved_submissions(self, username, since=None, limit=100):
                return [
                    {
                        "platform_id": "java-singleton",
                        "title": "Java Singleton Pattern",
                        "url": "https://www.hackerrank.com/challenges/java-singleton",
                        "solved_at": None,
                    }
                ]

        with patch.dict(SyncService.PLATFORM_SERVICES, {"hackerrank": FakeHackerRankService}):
            result = SyncService.sync_user_platform(self.user, "hackerrank")

        self.assertEqual(result["status"], "success")
        self.assertEqual(UserSolvedProblem.objects.filter(user=self.user).count(), 1)
        self.assertEqual(RevisionItem.objects.filter(revision_list__user=self.user).count(), 1)
