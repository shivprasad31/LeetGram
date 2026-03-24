from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Group, GroupChallenge, GroupInvite, GroupMembership, GroupTask


class GroupMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "group", "user", "username", "role", "joined_at", "is_muted", "total_challenges", "challenge_wins"]
        read_only_fields = ["joined_at"]


class GroupInviteSerializer(serializers.ModelSerializer):
    invitee_username = serializers.CharField(source="invitee.username", read_only=True)
    invited_by_username = serializers.CharField(source="invited_by.username", read_only=True)

    class Meta:
        model = GroupInvite
        fields = ["id", "group", "invited_by", "invited_by_username", "invitee", "invitee_username", "status", "created_at"]
        read_only_fields = ["invited_by", "status", "created_at"]


class GroupTaskSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = GroupTask
        fields = ["id", "group", "created_by", "created_by_username", "title", "description", "difficulty", "link", "created_at"]
        read_only_fields = ["created_by", "created_at"]


class GroupChallengeSerializer(serializers.ModelSerializer):
    challenger_username = serializers.CharField(source="challenger.username", read_only=True)
    opponent_username = serializers.CharField(source="opponent.username", read_only=True)
    problem_name = serializers.CharField(source="problem.canonical_name", read_only=True)

    class Meta:
        model = GroupChallenge
        fields = ["id", "group", "challenger", "challenger_username", "opponent", "opponent_username", "problem", "problem_name", "status", "created_at"]
        read_only_fields = ["challenger", "status", "created_at"]


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

    def get_queryset(self):
        return Group.objects.select_related("owner").filter(memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        group = serializer.save(owner=self.request.user)
        GroupMembership.objects.get_or_create(group=group, user=self.request.user, defaults={"role": "owner"})

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        group = self.get_object()
        serializer = GroupTaskSerializer(group.tasks.select_related("created_by"), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def challenges(self, request, pk=None):
        group = self.get_object()
        serializer = GroupChallengeSerializer(group.group_challenges.select_related("challenger", "opponent", "problem"), many=True)
        return Response(serializer.data)


class GroupMembershipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GroupMembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GroupMembership.objects.select_related("group", "user").filter(user=self.request.user)


class GroupInviteViewSet(viewsets.ModelViewSet):
    serializer_class = GroupInviteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GroupInvite.objects.select_related("group", "invitee", "invited_by").filter(
            Q(invitee=self.request.user) | Q(invited_by=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.save(invited_by=self.request.user)
