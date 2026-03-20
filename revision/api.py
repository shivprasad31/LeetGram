from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import RevisionItem, RevisionList, RevisionNotes
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


class RevisionNotesSerializer(serializers.ModelSerializer):
    problem_title = serializers.CharField(source="problem.title", read_only=True)

    class Meta:
        model = RevisionNotes
        fields = ["id", "problem", "problem_title", "notes", "memory_hook", "updated_at"]


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


class RevisionNotesViewSet(viewsets.ModelViewSet):
    serializer_class = RevisionNotesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RevisionNotes.objects.filter(user=self.request.user).select_related("problem")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

