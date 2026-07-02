from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0041_externalintegration_auto_sync"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="crm_provider",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="CRM source for this order (hubspot, salesforce, zoho, etc.).",
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="crm_owner_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="CRM owner/user id at import time (audit trail).",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="external_integration",
            field=models.ForeignKey(
                blank=True,
                help_text="Integration that imported this order, when applicable.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="imported_orders",
                to="commissions.externalintegration",
            ),
        ),
        migrations.AlterField(
            model_name="externalintegration",
            name="provider",
            field=models.CharField(
                choices=[
                    ("salesforce", "Salesforce"),
                    ("generic_rest", "Generic REST API"),
                    ("webhook", "Webhook / Zapier"),
                    ("hubspot", "HubSpot (REST)"),
                    ("zoho", "Zoho CRM"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
