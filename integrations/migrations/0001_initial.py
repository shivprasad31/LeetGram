from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("codeforces", "Codeforces"), ("leetcode", "LeetCode"), ("gfg", "GeeksForGeeks"), ("hackerrank", "HackerRank")], max_length=32)),
                ("last_synced", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("success", "Success"), ("failed", "Failed")], default="success", max_length=16)),
                ("error_message", models.TextField(blank=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integration_statuses", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["user_id", "platform"],
                "indexes": [models.Index(fields=["platform", "last_synced"], name="integrations_platform_6f8149_idx"), models.Index(fields=["user", "platform"], name="integrations_user_id_4c7b58_idx")],
                "unique_together": {("user", "platform")},
            },
        ),
    ]