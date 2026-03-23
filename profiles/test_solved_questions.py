from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from problems.models import PlatformProblem, Problem, UserSolvedProblem
from problems.services import get_standard_difficulty
from users.models import User


class ProfileSolvedQuestionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="solved@example.com",
            username="solved-user",
            password="strong-pass-123",
        )
        self.easy = get_standard_difficulty("easy")
        self.medium = get_standard_difficulty("medium")
        self.hard = get_standard_difficulty("hard")

        self.easy_problem = Problem.objects.create(canonical_name="Two Sum", difficulty=self.easy)
        self.medium_problem = Problem.objects.create(canonical_name="Binary Tree Zigzag", difficulty=self.medium)
        self.hard_problem = Problem.objects.create(canonical_name="Merge K Lists", difficulty=self.hard)

        self.easy_platform_problem = PlatformProblem.objects.create(
            platform="leetcode",
            platform_id="two-sum",
            title="Two Sum",
            url="https://leetcode.com/problems/two-sum/",
            problem=self.easy_problem,
        )
        self.medium_platform_problem = PlatformProblem.objects.create(
            platform="codeforces",
            platform_id="123A",
            title="Binary Tree Zigzag",
            url="https://codeforces.com/problemset/problem/123/A",
            problem=self.medium_problem,
        )
        self.hard_platform_problem = PlatformProblem.objects.create(
            platform="gfg",
            platform_id="700001",
            title="Merge K Lists",
            url="https://www.geeksforgeeks.org/problems/merge-k-sorted-linked-lists/1",
            problem=self.hard_problem,
        )

        UserSolvedProblem.objects.create(user=self.user, platform_problem=self.easy_platform_problem, solved_at=timezone.now())
        UserSolvedProblem.objects.create(user=self.user, platform_problem=self.medium_platform_problem, solved_at=timezone.now())
        UserSolvedProblem.objects.create(user=self.user, platform_problem=self.hard_platform_problem, solved_at=timezone.now())

    def test_profile_detail_uses_dynamic_difficulty_counts(self):
        response = self.client.get(reverse("profiles:detail", args=[self.user.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["overall_solved_count"], 3)
        self.assertEqual(response.context["easy_solved_count"], 1)
        self.assertEqual(response.context["medium_solved_count"], 1)
        self.assertEqual(response.context["hard_solved_count"], 1)

    def test_solved_questions_page_supports_combined_filters(self):
        response = self.client.get(
            reverse("profiles:solved", args=[self.user.username]),
            {"q": "merge", "platform": "gfg", "difficulty": "hard"},
        )

        self.assertEqual(response.status_code, 200)
        solved_questions = list(response.context["solved_questions"])
        self.assertEqual(len(solved_questions), 1)
        self.assertEqual(solved_questions[0].platform_problem.problem.canonical_name, "Merge K Lists")
