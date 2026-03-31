from django.db.models import Q

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from problems.models import UserSolvedProblem

from .models import RevisionItem, RevisionList, RevisionNote
from .services import review_revision_item


class RevisionItemSerializer(serializers.ModelSerializer):
    problem_title = serializers.CharField(source="problem.title", read_only=True)

    class Meta:
        model = RevisionItem
        fields = ["id", "revision_list", "problem", "problem_title", "next_review_at", "last_reviewed_at", "interval_days", "ease_factor", "repetitions", "priority", "is_mastered"]


class RevisionListSerializer(serializers.ModelSerializer):
    items = RevisionItemSerializer(many=True, read_only=True)

    class Meta:
        model = RevisionList
        fields = ["id", "title", "description", "is_default", "created_at", "items"]


class RevisionNoteSerializer(serializers.ModelSerializer):
    problem_title = serializers.CharField(source="problem.title", read_only=True)

    class Meta:
        model = RevisionNote
        fields = ["id", "problem", "problem_title", "note_text", "updated_at"]


class RevisionProblemSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="platform_problem.problem.canonical_name", read_only=True)
    platform = serializers.CharField(source="platform_problem.platform", read_only=True)
    difficulty = serializers.CharField(source="platform_problem.problem.difficulty.name", read_only=True)
    difficulty_slug = serializers.CharField(source="platform_problem.problem.difficulty.slug", read_only=True)
    problem_id = serializers.IntegerField(source="platform_problem.problem_id", read_only=True)
    problem_url = serializers.SerializerMethodField()
    note_text = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()

    class Meta:
        model = UserSolvedProblem
        fields = ["id", "problem_id", "title", "platform", "difficulty", "difficulty_slug", "problem_url", "solved_at", "note_text", "topics"]

    def get_problem_url(self, obj):
        if obj.platform_problem and obj.platform_problem.url:
            return obj.platform_problem.url
        if obj.platform_problem and obj.platform_problem.problem:
            return f"/problems/{obj.platform_problem.problem.slug}/"
        return ""

    def get_note_text(self, obj):
        notes = self.context.get("note_map", {})
        return notes.get(obj.platform_problem.problem_id, "")

    def get_topics(self, obj):
        if not obj.platform_problem or not obj.platform_problem.problem_id:
            return []
        return [tag.name for tag in obj.platform_problem.problem.tags.all()]


class RevisionListViewSet(viewsets.ModelViewSet):
    serializer_class = RevisionListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RevisionList.objects.filter(user=self.request.user).prefetch_related("items__problem")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RevisionItemViewSet(viewsets.ModelViewSet):
    serializer_class = RevisionItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RevisionItem.objects.filter(revision_list__user=self.request.user).select_related("problem", "revision_list")

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        item = review_revision_item(self.get_object(), request.data.get("quality", 3))
        return Response(self.get_serializer(item).data)


class RevisionNoteViewSet(viewsets.ModelViewSet):
    serializer_class = RevisionNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RevisionNote.objects.filter(user=self.request.user).select_related("problem")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RevisionProblemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RevisionProblemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            UserSolvedProblem.objects.filter(user=self.request.user)
            .select_related("platform_problem", "platform_problem__problem", "platform_problem__problem__difficulty")
            .prefetch_related("platform_problem__problem__tags")
            .order_by("-solved_at", "platform_problem__problem__canonical_name")
        )
        search = self.request.query_params.get("search", "").strip()
        platform = self.request.query_params.get("platform", "").strip()
        difficulty = self.request.query_params.get("difficulty", "").strip()
        topic = self.request.query_params.get("topic", "").strip()
        if search:
            queryset = queryset.filter(
                Q(platform_problem__problem__canonical_name__icontains=search)
                | Q(platform_problem__title__icontains=search)
            )
        if platform:
            queryset = queryset.filter(platform_problem__platform=platform)
        if difficulty:
            queryset = queryset.filter(platform_problem__problem__difficulty__slug=difficulty)
        if topic:
            queryset = queryset.filter(platform_problem__problem__tags__slug=topic)
        return queryset.distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        note_map = {
            note.problem_id: note.note_text
            for note in RevisionNote.objects.filter(user=self.request.user)
        }
        context["note_map"] = note_map
        return context
