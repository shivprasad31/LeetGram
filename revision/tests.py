from django.test import TestCase
from django.urls import reverse

from problems.models import PlatformProblem, Problem, ProblemDifficulty, Tag, UserSolvedProblem
from users.models import User

from .models import RevisionNote


class RevisionDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="revision@example.com",
            username="revision-user",
            password="strong-pass-123",
        )
        self.client.force_login(self.user)

        easy, _ = ProblemDifficulty.objects.get_or_create(name="Easy", slug="easy", defaults={"weight": 1})
        medium, _ = ProblemDifficulty.objects.get_or_create(name="Medium", slug="medium", defaults={"weight": 2})
        arrays, _ = Tag.objects.get_or_create(name="Arrays", slug="arrays")
        graph, _ = Tag.objects.get_or_create(name="Graph", slug="graph")

        first_problem = Problem.objects.create(canonical_name="Two Sum", difficulty=easy)
        first_problem.tags.add(arrays)
        second_problem = Problem.objects.create(canonical_name="Clone Graph", difficulty=medium)
        second_problem.tags.add(graph)

        first_platform = PlatformProblem.objects.create(
            platform="leetcode",
            platform_id="1",
            title="Two Sum",
            url="https://leetcode.com/problems/two-sum/",
            problem=first_problem,
        )
        second_platform = PlatformProblem.objects.create(
            platform="leetcode",
            platform_id="133",
            title="Clone Graph",
            url="https://leetcode.com/problems/clone-graph/",
            problem=second_problem,
        )

        UserSolvedProblem.objects.create(user=self.user, platform_problem=first_platform)
        UserSolvedProblem.objects.create(user=self.user, platform_problem=second_platform)
        RevisionNote.objects.create(user=self.user, problem=first_problem, note_text="Watch the hashmap edge case.")

    def test_revision_page_lists_solved_problems_and_saved_notes(self):
        response = self.client.get(reverse("revision:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Two Sum")
        self.assertContains(response, "Clone Graph")
        self.assertContains(response, "Watch the hashmap edge case.")

    def test_revision_page_filters_by_search_and_topic(self):
        response = self.client.get(reverse("revision:index"), {"search": "clone", "topic": "graph"})

        self.assertContains(response, "Clone Graph")
        self.assertNotContains(response, "Two Sum")

    def test_revision_note_can_be_updated_from_dashboard(self):
        problem = Problem.objects.get(canonical_name="Clone Graph")
        response = self.client.post(
            reverse("revision:index"),
            {"problem_id": problem.id, "note_text": "Rebuild adjacency before DFS."},
        )

        self.assertRedirects(response, reverse("revision:index"))
        self.assertEqual(
            RevisionNote.objects.get(user=self.user, problem=problem).note_text,
            "Rebuild adjacency before DFS.",
        )

    def test_revision_problem_api_returns_note_text(self):
        response = self.client.get(reverse("revision-problem-list"))

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 2)
        two_sum = next(item for item in results if item["title"] == "Two Sum")
        self.assertEqual(two_sum["note_text"], "Watch the hashmap edge case.")
