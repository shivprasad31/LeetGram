from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import Group
from problems.models import Problem
from users.models import User

from .models import Challenge, ChallengeEvent, ChallengeResult, ChallengeSubmission
from .services import (
    accept_challenge,
    build_challenge_payload,
    challenge_queryset_for,
    create_challenge,
    forfeit_challenge,
    log_challenge_event,
    reject_challenge,
    run_code_for_problem,
    start_challenge,
    submit_challenge_code,
    update_challenge_presence,
)


class ChallengeSubmissionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ChallengeSubmission
        fields = [
            "id",
            "user",
            "username",
            "language",
            "verdict",
            "execution_time",
            "is_correct",
            "time_taken_seconds",
            "output",
            "error_output",
            "submitted_at",
        ]


class ChallengeResultSerializer(serializers.ModelSerializer):
    winner_name = serializers.CharField(source="winner.username", read_only=True)
    loser_name = serializers.CharField(source="loser.username", read_only=True)

    class Meta:
        model = ChallengeResult
        fields = ["id", "challenge", "winner", "winner_name", "loser", "loser_name", "time_taken", "created_at"]


class ChallengeEventSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ChallengeEvent
        fields = ["id", "user", "username", "event_type", "metadata", "timestamp"]


class ChallengeSerializer(serializers.ModelSerializer):
    challenger_name = serializers.CharField(source="challenger.username", read_only=True)
    opponent_name = serializers.CharField(source="opponent.username", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    winner_name = serializers.CharField(source="winner.username", read_only=True)
    disqualified_user_name = serializers.CharField(source="disqualified_user.username", read_only=True)
    result = ChallengeResultSerializer(read_only=True)
    latest_submissions = serializers.SerializerMethodField()

    opponent_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="opponent", write_only=True)
    group_id = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), source="group", write_only=True, required=False, allow_null=True)

    class Meta:
        model = Challenge
        fields = [
            "id",
            "challenger",
            "challenger_name",
            "opponent",
            "opponent_name",
            "opponent_id",
            "group",
            "group_name",
            "group_id",
            "problem",
            "status",
            "finish_reason",
            "allowed_language",
            "winner",
            "winner_name",
            "disqualified_user",
            "disqualified_user_name",
            "title_snapshot",
            "statement_snapshot",
            "constraints_snapshot",
            "created_at",
            "accepted_at",
            "challenger_joined_at",
            "opponent_joined_at",
            "start_time",
            "end_time",
            "result",
            "latest_submissions",
        ]
        read_only_fields = [
            "challenger",
            "opponent",
            "group",
            "problem",
            "status",
            "finish_reason",
            "allowed_language",
            "winner",
            "disqualified_user",
            "title_snapshot",
            "statement_snapshot",
            "constraints_snapshot",
            "created_at",
            "accepted_at",
            "challenger_joined_at",
            "opponent_joined_at",
            "start_time",
            "end_time",
            "result",
        ]

    def get_latest_submissions(self, obj):
        submissions = obj.submissions.select_related("user").order_by("-submitted_at")[:4]
        return ChallengeSubmissionSerializer(submissions, many=True).data


class SubmitChallengeSerializer(serializers.Serializer):
    code = serializers.CharField()
    language = serializers.ChoiceField(choices=Challenge.LANGUAGE_CHOICES, default=Challenge.LANGUAGE_PYTHON)


class RunCodeSerializer(serializers.Serializer):
    problem_id = serializers.PrimaryKeyRelatedField(queryset=Problem.objects.all(), source="problem")
    code = serializers.CharField()
    language = serializers.ChoiceField(choices=Challenge.LANGUAGE_CHOICES, default=Challenge.LANGUAGE_PYTHON)


class ChallengeEventCreateSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=ChallengeEvent.EVENT_CHOICES)
    metadata = serializers.JSONField(required=False)


class ChallengePresenceSerializer(serializers.Serializer):
    camera_active = serializers.BooleanField()
    snapshot_data = serializers.CharField(required=False, allow_blank=True)


class ChallengeViewSet(viewsets.ModelViewSet):
    serializer_class = ChallengeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return challenge_queryset_for(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = create_challenge(
                challenger=request.user,
                opponent=serializer.validated_data["opponent"],
                group=serializer.validated_data.get("group"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        return Response(self.get_serializer(challenge).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def accept_challenge(self, request, pk=None):
        challenge = self.get_object()
        try:
            challenge = accept_challenge(challenge, request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        return Response(self.get_serializer(challenge).data)

    @action(detail=True, methods=["post"])
    def reject_challenge(self, request, pk=None):
        challenge = self.get_object()
        try:
            challenge = reject_challenge(challenge, request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        return Response(self.get_serializer(challenge).data)

    @action(detail=True, methods=["post"])
    def start_challenge(self, request, pk=None):
        challenge = self.get_object()
        try:
            challenge = start_challenge(challenge, request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        return Response(build_challenge_payload(challenge, current_user=request.user))

    @action(detail=True, methods=["post"])
    def submit_code(self, request, pk=None):
        challenge = self.get_object()
        serializer = SubmitChallengeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submission = submit_challenge_code(
                challenge=challenge,
                user=request.user,
                code=serializer.validated_data["code"],
                language=serializer.validated_data["language"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        submission_payload = ChallengeSubmissionSerializer(submission).data
        submission_payload["results"] = getattr(submission, "execution_details", {}).get("results", [])
        submission_payload["passed_count"] = getattr(submission, "execution_details", {}).get("passed_count", 0)
        submission_payload["failed_count"] = getattr(submission, "execution_details", {}).get("failed_count", 0)
        submission_payload["supported"] = getattr(submission, "execution_details", {}).get("supported", True)
        return Response(submission_payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def forfeit(self, request, pk=None):
        challenge = self.get_object()
        try:
            forfeit_challenge(challenge, request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        challenge.refresh_from_db()
        return Response(build_challenge_payload(challenge, current_user=request.user))

    @action(detail=True, methods=["post"])
    def presence(self, request, pk=None):
        challenge = self.get_object()
        serializer = ChallengePresenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = update_challenge_presence(
                challenge,
                request.user,
                camera_active=serializer.validated_data["camera_active"],
                snapshot_data=serializer.validated_data.get("snapshot_data", ""),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message if hasattr(exc, "message") else str(exc))
        return Response(build_challenge_payload(challenge, current_user=request.user))

    @action(detail=True, methods=["get"])
    def get_result(self, request, pk=None):
        challenge = self.get_object()
        return Response(build_challenge_payload(challenge, current_user=request.user))

    @action(detail=True, methods=["post"])
    def events(self, request, pk=None):
        challenge = self.get_object()
        serializer = ChallengeEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = log_challenge_event(
            challenge=challenge,
            user=request.user,
            event_type=serializer.validated_data["event_type"],
            metadata=serializer.validated_data.get("metadata", {}),
        )
        return Response(ChallengeEventSerializer(event).data, status=status.HTTP_201_CREATED)


class ChallengeResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChallengeResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChallengeResult.objects.filter(
            challenge__in=challenge_queryset_for(self.request.user)
        ).select_related("challenge", "winner", "loser")


class ChallengeSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChallengeSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ChallengeSubmission.objects.filter(
            challenge__in=challenge_queryset_for(self.request.user)
        ).select_related("user", "challenge")
        challenge_id = self.request.query_params.get("challenge")
        if challenge_id:
            queryset = queryset.filter(challenge_id=challenge_id)
        return queryset


class ChallengeEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChallengeEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        challenge_id = self.request.query_params.get("challenge")
        queryset = ChallengeEvent.objects.filter(
            challenge__in=challenge_queryset_for(self.request.user)
        ).select_related("user", "challenge")
        if challenge_id:
            queryset = queryset.filter(challenge_id=challenge_id)
        return queryset


class RunCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RunCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        execution = run_code_for_problem(
            serializer.validated_data["problem"],
            serializer.validated_data["code"],
            serializer.validated_data["language"],
        )
        execution["problem_id"] = serializer.validated_data["problem"].id
        return Response(execution)
