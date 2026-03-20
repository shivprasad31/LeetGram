from django.core.exceptions import ValidationError
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import User

from .models import FriendRequest, Friendship
from .services import accept_friend_request, remove_friendship, send_friend_request


class FriendRequestSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)
    receiver_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True, source="receiver")

    class Meta:
        model = FriendRequest
        fields = ["id", "sender_username", "receiver_username", "receiver_id", "message", "status", "created_at"]
        read_only_fields = ["status", "created_at"]


class FriendshipSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ["id", "friend", "created_at"]

    def get_friend(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        friend = obj.user_two if user == obj.user_one else obj.user_one
        return {"id": friend.id, "username": friend.username, "rating": friend.rating}


class FriendRequestViewSet(viewsets.ModelViewSet):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FriendRequest.objects.filter(Q(sender=user) | Q(receiver=user)).select_related("sender", "receiver")

    @ratelimit(key="user", rate="10/h", method="POST", block=True)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            friend_request = send_friend_request(request.user, serializer.validated_data["receiver"], serializer.validated_data.get("message", ""))
        except ValidationError as exc:
            raise serializers.ValidationError(exc.message)
        return Response(self.get_serializer(friend_request).data, status=201)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        friend_request = self.get_object()
        accept_friend_request(friend_request)
        return Response(self.get_serializer(friend_request).data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        friend_request = self.get_object()
        friend_request.mark("declined")
        return Response(self.get_serializer(friend_request).data)


class FriendshipViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Friendship.objects.filter(Q(user_one=user) | Q(user_two=user)).select_related("user_one", "user_two")

    def destroy(self, request, *args, **kwargs):
        friendship = self.get_object()
        friend = friendship.user_two if friendship.user_one == request.user else friendship.user_one
        remove_friendship(request.user, friend)
        return Response(status=204)
