from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from friends.models import Friendship
from groups.models import Group, GroupMembership
from problems.models import PlatformProblem, Problem, ProblemDifficulty, UserSolvedProblem
from profiles.models import ProfileStatistics
from users.models import User

from .models import Challenge
from .services import accept_challenge, create_challenge, start_challenge, submit_challenge_code


@override_settings(CHALLENGE_USE_DOCKER=False, CHALLENGE_EXECUTION_TIMEOUT_SECONDS=3)
class ChallengeBattleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.challenger = User.objects.create_user(email="a@example.com", username="alpha", password="pass12345")
        self.opponent = User.objects.create_user(email="b@example.com", username="beta", password="pass12345")
        Friendship.objects.create(user_one=self.challenger, user_two=self.opponent)

        difficulty, _ = ProblemDifficulty.objects.get_or_create(name="Easy", slug="easy", defaults={"weight": 1})
        self.problem = Problem.objects.create(
            canonical_name="Add Two Numbers",
            difficulty=difficulty,
            statement="Return the sum of two space-separated integers.",
        )
        platform_problem = PlatformProblem.objects.create(
            platform="custom",
            platform_id="sum-1",
            title="Add Two Numbers",
            problem=self.problem,
        )
        UserSolvedProblem.objects.create(user=self.challenger, platform_problem=platform_problem)
        UserSolvedProblem.objects.create(user=self.opponent, platform_problem=platform_problem)

        self.test_cases = [
            {"input": "2 3", "output": "5", "is_public": True},
            {"input": "10 4", "output": "14", "is_public": False},
        ]

    def test_create_challenge_uses_shared_problem_pool(self):
        challenge = create_challenge(self.challenger, self.opponent, test_cases=self.test_cases)

        self.assertEqual(challenge.problem, self.problem)
        self.assertEqual(challenge.title_snapshot, self.problem.canonical_name)
        self.assertEqual(len(challenge.public_test_cases), 1)
        self.assertEqual(challenge.status, Challenge.STATUS_PENDING)

    def test_submit_correct_solution_finishes_challenge_and_updates_stats(self):
        challenge = create_challenge(self.challenger, self.opponent, test_cases=self.test_cases)
        accept_challenge(challenge, self.opponent)
        start_challenge(challenge, self.challenger)
        challenge = start_challenge(challenge, self.opponent)

        submission = submit_challenge_code(
            challenge,
            self.challenger,
            "def solve(raw_input: str) -> str:\n    a, b = map(int, raw_input.split())\n    return str(a + b)\n",
        )
        challenge.refresh_from_db()

        self.assertTrue(submission.is_correct)
        self.assertEqual(challenge.status, Challenge.STATUS_FINISHED)
        self.assertEqual(challenge.winner, self.challenger)
        self.assertEqual(challenge.result.winner, self.challenger)

        challenger_stats = ProfileStatistics.objects.get(user=self.challenger)
        opponent_stats = ProfileStatistics.objects.get(user=self.opponent)
        challenger_stats.refresh_from_db()
        opponent_stats.refresh_from_db()
        self.assertEqual(challenger_stats.total_challenges, 1)
        self.assertEqual(challenger_stats.challenge_wins, 1)
        self.assertEqual(opponent_stats.total_challenges, 1)

    def test_group_challenge_updates_group_membership_stats(self):
        group = Group.objects.create(name="Battle Squad", owner=self.challenger)
        GroupMembership.objects.create(group=group, user=self.challenger, role="owner")
        GroupMembership.objects.create(group=group, user=self.opponent, role="member")

        challenge = create_challenge(self.challenger, self.opponent, group=group, test_cases=self.test_cases)
        accept_challenge(challenge, self.opponent)
        start_challenge(challenge, self.challenger)
        challenge = start_challenge(challenge, self.opponent)

        submit_challenge_code(
            challenge,
            self.opponent,
            "def solve(raw_input: str) -> str:\n    left, right = map(int, raw_input.split())\n    return str(left + right)\n",
        )

        self.assertEqual(GroupMembership.objects.get(group=group, user=self.opponent).challenge_wins, 1)
        self.assertEqual(GroupMembership.objects.get(group=group, user=self.opponent).total_challenges, 1)
        self.assertEqual(GroupMembership.objects.get(group=group, user=self.challenger).total_challenges, 1)

    def test_api_flow_returns_submission_and_result_payload(self):
        self.client.force_authenticate(user=self.challenger)
        create_response = self.client.post(
            "/api/challenges/",
            {"opponent_id": self.opponent.id, "test_cases": self.test_cases},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        challenge_id = create_response.data["id"]

        self.client.force_authenticate(user=self.opponent)
        accept_response = self.client.post(f"/api/challenges/{challenge_id}/accept_challenge/")
        self.assertEqual(accept_response.status_code, 200)
        self.client.post(f"/api/challenges/{challenge_id}/start_challenge/")

        self.client.force_authenticate(user=self.challenger)
        self.client.post(f"/api/challenges/{challenge_id}/start_challenge/")
        submit_response = self.client.post(
            f"/api/challenges/{challenge_id}/submit_code/",
            {
                "code": "def solve(raw_input: str) -> str:\n    x, y = map(int, raw_input.split())\n    return str(x + y)\n",
                "language": "python",
            },
            format="json",
        )
        self.assertEqual(submit_response.status_code, 201)
        self.assertEqual(submit_response.data["verdict"], "correct")

        result_response = self.client.get(f"/api/challenges/{challenge_id}/get_result/")
        self.assertEqual(result_response.status_code, 200)
        self.assertEqual(result_response.data["status"], "finished")
        self.assertEqual(result_response.data["result"]["winner_name"], self.challenger.username)
