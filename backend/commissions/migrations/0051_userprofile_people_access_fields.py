from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0050_order_transaction_ops_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="department",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Department / org unit (People & Access).",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="account_status",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Optional override: active, suspended, deactivated.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="commission_eligible",
            field=models.BooleanField(
                default=True,
                help_text="Whether this person is eligible for commission calculations.",
            ),
        ),
    ]
