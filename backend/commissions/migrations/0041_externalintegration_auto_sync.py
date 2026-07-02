from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0040_userprofile_crm_alt_user_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalintegration",
            name="auto_sync_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Periodically pull CRM users and deals into Incentra.",
            ),
        ),
        migrations.AddField(
            model_name="externalintegration",
            name="auto_sync_interval_minutes",
            field=models.PositiveIntegerField(
                default=15,
                help_text="Minimum minutes between automatic sync runs.",
            ),
        ),
        migrations.AddField(
            model_name="externalintegration",
            name="last_auto_sync_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
