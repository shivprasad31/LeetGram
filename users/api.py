from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Badge, User, UserBadge


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ["id", "name", "slug", "description", "category", "icon", "threshold"]


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ["id", "badge", "awarded_at"]


class UserSerializer(serializers.ModelSerializer):
    awards = UserBadgeSerializer(source="badges", many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "rating",
            "rank",
            "streak",
            "solved_count",
            "avatar",
            "bio",
            "github",
            "linkedin",
            "leetcode_username",
            "codeforces_username",
            "gfg_username",
            "created_at",
            "email_verified",
            "awards",
        ]


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password", "bio"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @ratelimit(key="ip", rate="5/h", method="POST", block=True)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("-rating")
    search_fields = ["username", "email"]
    ordering_fields = ["rating", "solved_count", "streak", "created_at"]

    @action(detail=False, permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)
