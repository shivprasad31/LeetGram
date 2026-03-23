from django.db import models
from rest_framework import filters, serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Problem, ProblemDifficulty, Tag, UserSolvedProblem, PlatformProblem


class ProblemDifficultySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProblemDifficulty
        fields = ["id", "name", "slug", "weight", "color"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "color"]


class PlatformProblemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformProblem
        fields = ["id", "platform", "platform_id", "title", "url"]


class ProblemSerializer(serializers.ModelSerializer):
    difficulty = ProblemDifficultySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    platforms = PlatformProblemSerializer(many=True, read_only=True, source="platform_problems")

    class Meta:
        model = Problem
        fields = [
            "id", 
            "canonical_name", 
            "slug", 
            "statement", 
            "difficulty", 
            "tags", 
            "platforms",
            "created_at"
        ]


class UserSolvedProblemSerializer(serializers.ModelSerializer):
    platform_problem = PlatformProblemSerializer(read_only=True)
    canonical_problem = serializers.CharField(source="platform_problem.problem.canonical_name", read_only=True)
    difficulty = serializers.CharField(source="platform_problem.problem.difficulty.name", read_only=True)
    platform = serializers.CharField(source="platform_problem.platform", read_only=True)
    problem_url = serializers.CharField(source="platform_problem.url", read_only=True)

    class Meta:
        model = UserSolvedProblem
        fields = [
            "id", 
            "platform_problem", 
            "canonical_problem",
            "platform",
            "difficulty",
            "problem_url",
            "solved_at", 
            "runtime_ms", 
            "memory_kb", 
            "language",
            "notes"
        ]


class ProblemDifficultyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProblemDifficultySerializer
    queryset = ProblemDifficulty.objects.all()


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()


class ProblemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProblemSerializer
    queryset = Problem.objects.select_related("difficulty").prefetch_related("tags").all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["canonical_name", "platform_problems__title"]
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
        queryset = UserSolvedProblem.objects.select_related(
            "platform_problem",
            "platform_problem__problem",
            "platform_problem__problem__difficulty",
        ).filter(user=self.request.user)
        platform = self.request.query_params.get("platform")
        difficulty = self.request.query_params.get("difficulty")
        search = self.request.query_params.get("q")
        if platform:
            queryset = queryset.filter(platform_problem__platform=platform)
        if difficulty:
            queryset = queryset.filter(platform_problem__problem__difficulty__slug=difficulty)
        if search:
            queryset = queryset.filter(
                models.Q(platform_problem__problem__canonical_name__icontains=search)
                | models.Q(platform_problem__title__icontains=search)
            )
        return queryset

