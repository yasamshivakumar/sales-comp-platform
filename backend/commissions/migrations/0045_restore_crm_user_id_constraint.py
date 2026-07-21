"""Restore CRM user-id uniqueness accidentally dropped by model drift in 0043."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0044_backfill_plan_versions"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(("crm_user_id__gt", "")),
                fields=("organization", "crm_user_id"),
                name="uniq_crm_user_id_per_org",
            ),
        ),
    ]
