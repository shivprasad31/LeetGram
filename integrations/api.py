import secrets

from django.urls import reverse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExternalProfileConnection
from .services import default_profile_url, ingest_leetcode_submission
from .tasks import sync_external_profile


class ExternalProfileConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalProfileConnection
        fields = [
            "id",
            "platform",
            "username",
            "profile_url",
            "api_token",
            "session_cookie",
            "is_active",
            "last_synced_at",
            "sync_status",
            "remote_rating",
            "remote_solved_count",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["profile_url", "api_token", "last_synced_at", "sync_status", "remote_rating", "remote_solved_count", "created_at"]


class LeetCodeQuestionSerializer(serializers.Serializer):
    question_id = serializers.CharField(required=False, allow_blank=True)
    frontend_question_id = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField()
    title_slug = serializers.CharField()
    difficulty = serializers.CharField(required=False, allow_blank=True)
    paid_only = serializers.BooleanField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    ac_rate = serializers.CharField(required=False, allow_blank=True)
    topic_tags = serializers.ListField(child=serializers.DictField(), required=False)


class LeetCodeSubmissionIngestSerializer(serializers.Serializer):
    submission_id = serializers.CharField()
    status_code = serializers.IntegerField(required=False)
    status_display = serializers.CharField(required=False, allow_blank=True)
    timestamp = serializers.IntegerField(required=False)
    runtime_ms = serializers.IntegerField(required=False, allow_null=True)
    memory_kb = serializers.IntegerField(required=False, allow_null=True)
    runtime_display = serializers.CharField(required=False, allow_blank=True)
    memory_display = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    lang = serializers.CharField(required=False, allow_blank=True)
    question = LeetCodeQuestionSerializer()


class ExternalProfileConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = ExternalProfileConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExternalProfileConnection.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        connection = serializer.save(user=self.request.user)
        connection.profile_url = default_profile_url(connection.platform, connection.username)
        connection.save(update_fields=["profile_url"])

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        connection = self.get_object()
        sync_external_profile.delay(connection.id)
        return Response({"status": "queued"})

    @action(detail=True, methods=["post"], url_path="issue-token")
    def issue_token(self, request, pk=None):
        connection = self.get_object()
        should_rotate = str(request.data.get("rotate", "false")).lower() in {"1", "true", "yes"}
        if should_rotate or not connection.api_token:
            connection.api_token = secrets.token_urlsafe(32)
            connection.save(update_fields=["api_token"])
        return Response(
            {
                "api_token": connection.api_token,
                "endpoint": request.build_absolute_uri(reverse("api-leetcode-submission")),
                "connection_id": connection.id,
                "platform": connection.platform,
                "username": connection.username,
            }
        )


class LeetCodeSubmissionIngestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.headers.get("X-LeetGram-Token") or request.data.get("api_token")
        if not token:
            return Response({"detail": "Missing LeetGram integration token."}, status=401)

        connection = ExternalProfileConnection.objects.select_related("user").filter(
            platform="leetcode",
            api_token=token,
            is_active=True,
        ).first()
        if connection is None:
            return Response({"detail": "Invalid LeetGram integration token."}, status=401)

        serializer = LeetCodeSubmissionIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = ingest_leetcode_submission(connection, serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        status_code = 201 if result["created"] else 200
        return Response(result, status=status_code)
