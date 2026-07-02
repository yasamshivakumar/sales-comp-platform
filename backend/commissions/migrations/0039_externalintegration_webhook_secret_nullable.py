from django.db import migrations, models


def clear_empty_webhook_secrets(apps, schema_editor):
    ExternalIntegration = apps.get_model("commissions", "ExternalIntegration")
    ExternalIntegration.objects.filter(webhook_secret="").update(webhook_secret=None)


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0038_userprofile_crm_user_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externalintegration",
            name="webhook_secret",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(clear_empty_webhook_secrets, migrations.RunPython.noop),
    ]
