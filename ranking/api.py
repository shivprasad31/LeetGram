from rest_framework import serializers, viewsets

from .models import DailyRanking, GlobalLeaderboard, WeeklyRanking


class DailyRankingSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = DailyRanking
        fields = ["id", "date", "username", "score", "challenges_won", "contest_points", "solved_points", "streak_bonus", "rank"]


class WeeklyRankingSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = WeeklyRanking
        fields = ["id", "week_start", "username", "score", "challenges_won", "contest_points", "solved_points", "streak_bonus", "rank"]


class GlobalLeaderboardSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = GlobalLeaderboard
        fields = ["id", "username", "score", "total_solved", "challenges_won", "rank", "updated_at"]


class DailyRankingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DailyRankingSerializer
    queryset = DailyRanking.objects.select_related("user").order_by("rank")


class WeeklyRankingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WeeklyRankingSerializer
    queryset = WeeklyRanking.objects.select_related("user").order_by("rank")


class GlobalLeaderboardViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GlobalLeaderboardSerializer
    queryset = GlobalLeaderboard.objects.select_related("user").order_by("rank")

