from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0037_commission_calculation_scope_commission_currency_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="crm_user_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="External CRM owner/user ID (e.g. HubSpot owner id).",
                max_length=100,
            ),
        ),
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(crm_user_id__gt=""),
                fields=("organization", "crm_user_id"),
                name="uniq_crm_user_id_per_org",
            ),
        ),
    ]
