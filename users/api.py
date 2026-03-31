from rest_framework import generics, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from profiles.integrations import INTEGRATION_PLATFORMS, validate_integration_username

from .models import Badge, User, UserBadge
from .tasks import dispatch_user_sync


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
            "hackerrank_username",
            "last_synced_at",
            "created_at",
            "awards",
        ]


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "bio",
            "codeforces_username",
            "leetcode_username",
            "gfg_username",
            "hackerrank_username",
        ]

    def validate(self, attrs):
        seen = {}
        for field_name, meta in INTEGRATION_PLATFORMS.items():
            normalized = validate_integration_username(attrs.get(field_name), meta["label"])
            attrs[field_name] = normalized
            if not normalized:
                continue
            lookup = normalized.casefold()
            if lookup in seen:
                raise serializers.ValidationError(
                    {field_name: f"This username is already used for {seen[lookup]}. Use a distinct handle per platform."}
                )
            seen[lookup] = meta["label"]
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        if user.has_connected_profiles:
            dispatch_user_sync(user.id)
        return user


class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        return Response(
            {
                "detail": "Direct registration is disabled. Use the OTP signup flow at /send-otp/ and /verify-otp/.",
            },
            status=400,
        )


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all().order_by("-solved_count", "-streak", "username")
    search_fields = ["username", "email"]
    ordering_fields = ["solved_count", "streak", "created_at", "username"]

    @action(detail=False, permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user, context={"request": request}).data)
