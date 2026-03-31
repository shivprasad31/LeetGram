from rest_framework import serializers, viewsets

from .models import ProfileStatistics, UserActivity


class ProfileStatisticsSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ProfileStatistics
        fields = [
            "id",
            "username",
            "total_solved",
            "easy_solved",
            "medium_solved",
            "hard_solved",
            "total_challenges",
            "challenge_wins",
            "contests_participated",
            "contests_won",
        ]


class UserActivitySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserActivity
        fields = ["id", "username", "activity_type", "description", "metadata", "created_at"]


class ProfileStatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProfileStatisticsSerializer
    queryset = ProfileStatistics.objects.select_related("user").all()


class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserActivitySerializer

    def get_queryset(self):
        queryset = UserActivity.objects.select_related("user").all()
        username = self.request.query_params.get("user")
        if username:
            queryset = queryset.filter(user__username=username)
        return queryset

