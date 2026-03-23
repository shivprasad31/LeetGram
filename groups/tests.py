from django.test import TestCase
from django.urls import reverse

from users.models import User

from .models import Group, GroupMembership, GroupTask, GroupTaskCompletion


class GroupWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.com", username="owner", password="strong-pass-123")
        self.member = User.objects.create_user(email="member@example.com", username="member", password="strong-pass-123")
        self.group = Group.objects.create(name="Algo Squad", owner=self.owner)
        GroupMembership.objects.create(group=self.group, user=self.owner, role="owner")
        GroupMembership.objects.create(group=self.group, user=self.member, role="member")

    def test_only_admin_can_add_group_task(self):
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("groups:add_task"),
            {"group_slug": self.group.slug, "title": "Question of the Day"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(GroupTask.objects.count(), 0)

    def test_member_can_complete_group_task(self):
        task = GroupTask.objects.create(group=self.group, created_by=self.owner, title="Today's two pointer question")
        self.client.force_login(self.member)

        response = self.client.post(reverse("groups:complete_task", args=[task.id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(GroupTaskCompletion.objects.filter(task=task, user=self.member).exists())

    def test_group_details_payload_includes_members_tasks_and_activity(self):
        task = GroupTask.objects.create(group=self.group, created_by=self.owner, title="Tree revision")
        GroupTaskCompletion.objects.create(task=task, user=self.member)
        self.client.force_login(self.owner)

        response = self.client.get(reverse("groups:get_group_details", args=[self.group.slug]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["group"]
        self.assertEqual(payload["name"], self.group.name)
        self.assertEqual(len(payload["members"]), 2)
        self.assertEqual(payload["tasks"][0]["title"], "Tree revision")
