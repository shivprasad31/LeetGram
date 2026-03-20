from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from challenges.models import Challenge
from contests.models import Contest
from problems.services import recommend_problems_for_user
from ranking.services import score_breakdown_for_user

from .models import UserPreference


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ["theme_mode", "accent_color", "reduce_motion", "dashboard_layout", "updated_at"]
        read_only_fields = ["updated_at"]


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        recommended = recommend_problems_for_user(user)
        return Response(
            {
                "score_breakdown": score_breakdown_for_user(user),
                "active_challenges": Challenge.objects.filter(receiver=user).exclude(status="finished").count(),
                "upcoming_contests": Contest.objects.count(),
                "recommended_problems": [problem.title for problem in recommended],
            }
        )


class DashboardPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserPreferenceSerializer(request.user.preference).data)

    def post(self, request):
        serializer = UserPreferenceSerializer(request.user.preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

