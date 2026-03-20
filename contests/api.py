from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from problems.models import Problem, ProblemDifficulty

from .models import Contest, ContestLeaderboard, ContestParticipant, ContestProblem, ContestSubmission, ContestTeam
from .services import rebuild_contest_leaderboard, register_contest_activity


class ContestProblemSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="problem.title", read_only=True)

    class Meta:
        model = ContestProblem
        fields = ["id", "problem", "title", "order", "points"]


class ContestLeaderboardSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = ContestLeaderboard
        fields = ["id", "contest", "participant", "team", "label", "score", "penalty", "rank", "last_submission_at"]

    def get_label(self, obj):
        if obj.team:
            return obj.team.name
        if obj.participant:
            return obj.participant.user.username
        return "Unknown"


class ContestSerializer(serializers.ModelSerializer):
    problem_ids = serializers.PrimaryKeyRelatedField(queryset=Problem.objects.all(), many=True, write_only=True, required=False)
    contest_problems = ContestProblemSerializer(many=True, read_only=True)
    host_username = serializers.CharField(source="host.username", read_only=True)
    leaderboard = ContestLeaderboardSerializer(source="leaderboard_entries", many=True, read_only=True)
    difficulty_id = serializers.PrimaryKeyRelatedField(queryset=ProblemDifficulty.objects.all(), source="difficulty", write_only=True, required=False, allow_null=True)

    class Meta:
        model = Contest
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "host",
            "host_username",
            "group",
            "start_at",
            "duration_minutes",
            "difficulty",
            "difficulty_id",
            "visibility",
            "status",
            "is_team_based",
            "created_at",
            "contest_problems",
            "problem_ids",
            "leaderboard",
        ]
        read_only_fields = ["slug", "host", "created_at", "difficulty"]


class ContestSubmissionSerializer(serializers.ModelSerializer):
    contestant_label = serializers.SerializerMethodField()

    class Meta:
        model = ContestSubmission
        fields = ["id", "contest", "problem", "participant", "team", "contestant_label", "language", "code_snippet", "verdict", "score", "submitted_at"]
        read_only_fields = ["submitted_at"]

    def get_contestant_label(self, obj):
        if obj.team:
            return obj.team.name
        if obj.participant:
            return obj.participant.user.username
        return "Unknown"


class ContestViewSet(viewsets.ModelViewSet):
    serializer_class = ContestSerializer
    permission_classes = [IsAuthenticated]
    queryset = Contest.objects.select_related("host", "difficulty", "group").prefetch_related("contest_problems__problem", "leaderboard_entries").all()

    @transaction.atomic
    def perform_create(self, serializer):
        problem_ids = serializer.validated_data.pop("problem_ids", [])
        contest = serializer.save(host=self.request.user)
        for order, problem in enumerate(problem_ids, start=1):
            ContestProblem.objects.create(contest=contest, problem=problem, order=order, points=problem.points)

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        contest = self.get_object()
        team = None
        if contest.is_team_based:
            team_name = request.data.get("team_name") or f"Team {request.user.username}"
            team, _ = ContestTeam.objects.get_or_create(contest=contest, name=team_name, defaults={"captain": request.user, "group": contest.group})
        participant, _ = ContestParticipant.objects.get_or_create(contest=contest, user=request.user, defaults={"team": team})
        if team and participant.team != team:
            participant.team = team
            participant.save(update_fields=["team"])
        register_contest_activity(contest, request.user)
        return Response({"participant_id": participant.id})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        contest = self.get_object()
        participant = ContestParticipant.objects.filter(contest=contest, user=request.user).first()
        team = participant.team if participant else None
        submission = ContestSubmission.objects.create(
            contest=contest,
            problem_id=request.data.get("problem"),
            participant=participant,
            team=team,
            language=request.data.get("language", "python"),
            code_snippet=request.data.get("code_snippet", ""),
            verdict=request.data.get("verdict", "wrong_answer"),
            score=int(request.data.get("score", 0)),
        )
        rebuild_contest_leaderboard(contest)
        return Response(ContestSubmissionSerializer(submission).data, status=201)


class ContestSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContestSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ContestSubmission.objects.select_related("contest", "participant__user", "team", "problem")
        contest_id = self.request.query_params.get("contest")
        if contest_id:
            queryset = queryset.filter(contest_id=contest_id)
        return queryset.filter(participant__user=self.request.user) | queryset.filter(team__participants__user=self.request.user)


class ContestLeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContestLeaderboardSerializer
    queryset = ContestLeaderboard.objects.select_related("participant__user", "team", "contest").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        contest_id = self.request.query_params.get("contest")
        if contest_id:
            queryset = queryset.filter(contest_id=contest_id)
        return queryset

