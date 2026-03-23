from django.core.exceptions import ValidationError
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from problems.models import ProblemDifficulty
from users.models import User

from .models import Challenge, ChallengeProblem, ChallengeResult
from .services import accept_challenge, create_challenge, start_challenge, submit_challenge_result


class ChallengeProblemSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="problem.canonical_name", read_only=True)
    slug = serializers.CharField(source="problem.slug", read_only=True)

    class Meta:
        model = ChallengeProblem
        fields = ["id", "position", "problem", "title", "slug"]


class ChallengeResultSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ChallengeResult
        fields = ["id", "user", "username", "score", "solved_count", "completion_time_seconds", "submitted_at"]


class ChallengeSerializer(serializers.ModelSerializer):
    challenge_problems = ChallengeProblemSerializer(many=True, read_only=True)
    results = ChallengeResultSerializer(many=True, read_only=True)
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)
    receiver_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="receiver", write_only=True, required=False)
    difficulty_id = serializers.PrimaryKeyRelatedField(queryset=ProblemDifficulty.objects.all(), source="difficulty", write_only=True, required=False, allow_null=True)

    class Meta:
        model = Challenge
        fields = [
            "id",
            "sender",
            "sender_username",
            "receiver",
            "receiver_username",
            "receiver_id",
            "difficulty",
            "difficulty_id",
            "time_limit_minutes",
            "status",
            "winner",
            "created_at",
            "accepted_at",
            "started_at",
            "finished_at",
            "challenge_problems",
            "results",
        ]
        read_only_fields = ["sender", "receiver", "difficulty", "status", "winner", "created_at", "accepted_at", "started_at", "finished_at"]


class ChallengeViewSet(viewsets.ModelViewSet):
    serializer_class = ChallengeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Challenge.objects.filter(sender=user) | Challenge.objects.filter(receiver=user)

    @ratelimit(key="user", rate="8/h", method="POST", block=True)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = create_challenge(
                request.user,
                serializer.validated_data["receiver"],
                serializer.validated_data.get("difficulty"),
                serializer.validated_data.get("time_limit_minutes", 90),
            )
        except ValidationError as exc:
            raise serializers.ValidationError(exc.message)
        return Response(self.get_serializer(challenge).data, status=201)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        challenge = accept_challenge(self.get_object(), request.user)
        return Response(self.get_serializer(challenge).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        challenge = start_challenge(self.get_object())
        return Response(self.get_serializer(challenge).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        challenge = self.get_object()
        result = submit_challenge_result(
            challenge,
            request.user,
            int(request.data.get("score", 0)),
            int(request.data.get("solved_count", 0)),
            int(request.data.get("completion_time_seconds", 0)),
        )
        return Response(ChallengeResultSerializer(result).data)


class ChallengeResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChallengeResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChallengeResult.objects.filter(user=self.request.user).select_related("challenge", "user")

