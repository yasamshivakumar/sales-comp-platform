from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0039_externalintegration_webhook_secret_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="crm_alt_user_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Secondary CRM user id (e.g. HubSpot userId vs owner id on deals).",
                max_length=100,
            ),
        ),
    ]
