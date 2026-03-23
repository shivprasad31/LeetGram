from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("problems", "0003_platformproblem_rename_problemtag_tag_and_more"),
        ("groups", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("difficulty", models.CharField(blank=True, max_length=32)),
                ("link", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="created_group_tasks", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="groups.group")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="GroupChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("challenger", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_challenges_started", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_challenges", to="groups.group")),
                ("opponent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_challenges_received", to=settings.AUTH_USER_MODEL)),
                ("problem", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="group_challenges", to="problems.problem")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["group", "status", "-created_at"], name="groups_group_group_i_7fa622_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="groupchallenge",
            constraint=models.CheckConstraint(condition=models.Q(("challenger", models.F("opponent")), _negated=True), name="group_challenge_not_self"),
        ),
    ]