# Generated manually for compensation plan governance fields

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("commissions", "0048_marginal_rate_table_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="compensationplan",
            name="plan_type",
            field=models.CharField(
                choices=[
                    ("sales_commission", "Sales Commission"),
                    ("bonus_plan", "Bonus Plan"),
                    ("manager_override", "Manager Override"),
                    ("channel_incentive", "Channel Incentive"),
                    ("spiff", "SPIFF"),
                ],
                db_index=True,
                default="sales_commission",
                help_text="Business classification for catalog filtering and reporting.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="compensationplan",
            name="owner",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Owning team or function (e.g. Sales Operations).",
                max_length=150,
            ),
        ),
        migrations.AddField(
            model_name="compensationplan",
            name="approver",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Approving role or person (e.g. Finance Director).",
                max_length=150,
            ),
        ),
        migrations.AddField(
            model_name="compensationplan",
            name="last_modified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="modified_compensation_plans",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
