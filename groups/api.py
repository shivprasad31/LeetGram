from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Group, GroupInvite, GroupMembership


class GroupMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "group", "user", "username", "role", "joined_at", "is_muted"]
        read_only_fields = ["joined_at"]


class GroupInviteSerializer(serializers.ModelSerializer):
    invitee_username = serializers.CharField(source="invitee.username", read_only=True)

    class Meta:
        model = GroupInvite
        fields = ["id", "group", "invited_by", "invitee", "invitee_username", "status", "created_at"]
        read_only_fields = ["invited_by", "status", "created_at"]


class GroupSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "slug", "description", "avatar", "cover_image", "owner", "owner_username", "privacy", "member_count", "created_at"]
        read_only_fields = ["slug", "owner", "created_at"]

    def get_member_count(self, obj):
        return obj.memberships.count()


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]
    queryset = Group.objects.select_related("owner").all()

    @transaction.atomic
    def perform_create(self, serializer):
        group = serializer.save(owner=self.request.user)
        GroupMembership.objects.get_or_create(group=group, user=self.request.user, defaults={"role": "owner"})

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        group = self.get_object()
        membership, _ = GroupMembership.objects.get_or_create(group=group, user=request.user)
        return Response(GroupMembershipSerializer(membership).data)


class GroupMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GroupMembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GroupMembership.objects.select_related("group", "user").filter(user=self.request.user)


class GroupInviteViewSet(viewsets.ModelViewSet):
    serializer_class = GroupInviteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GroupInvite.objects.select_related("group", "invitee", "invited_by").filter(invitee=self.request.user)

    def perform_create(self, serializer):
        serializer.save(invited_by=self.request.user)
