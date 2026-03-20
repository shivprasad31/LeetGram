from rest_framework import filters, serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Problem, ProblemDifficulty, ProblemTag, UserSolvedProblem


class ProblemDifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProblemDifficulty
        fields = ["id", "name", "slug", "weight", "color"]


class ProblemTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProblemTag
        fields = ["id", "name", "slug", "color"]


class ProblemSerializer(serializers.ModelSerializer):
    difficulty = ProblemDifficultySerializer(read_only=True)
    tags = ProblemTagSerializer(many=True, read_only=True)

    class Meta:
        model = Problem
        fields = ["id", "external_id", "title", "slug", "statement", "url", "platform", "source", "difficulty", "tags", "acceptance_rate", "points", "is_premium", "created_at"]


class UserSolvedProblemSerializer(serializers.ModelSerializer):
    problem = ProblemSerializer(read_only=True)

    class Meta:
        model = UserSolvedProblem
        fields = ["id", "problem", "platform", "submission_id", "solved_at", "runtime_ms", "memory_kb", "notes", "source_rating_change"]


class ProblemDifficultyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProblemDifficultySerializer
    queryset = ProblemDifficulty.objects.all()


class ProblemTagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProblemTagSerializer
    queryset = ProblemTag.objects.all()


class ProblemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProblemSerializer
    queryset = Problem.objects.select_related("difficulty").prefetch_related("tags").all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "source", "platform"]
    ordering_fields = ["title", "created_at", "points"]

    def get_queryset(self):
        queryset = super().get_queryset()
        difficulty = self.request.query_params.get("difficulty")
        tag = self.request.query_params.get("tag")
        if difficulty:
            queryset = queryset.filter(difficulty__slug=difficulty)
        if tag:
            queryset = queryset.filter(tags__slug=tag)
        return queryset.distinct()


class UserSolvedProblemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSolvedProblemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = UserSolvedProblem.objects.select_related("problem__difficulty").prefetch_related("problem__tags").filter(user=self.request.user)
        platform = self.request.query_params.get("platform")
        if platform:
            queryset = queryset.filter(platform=platform)
        return queryset

