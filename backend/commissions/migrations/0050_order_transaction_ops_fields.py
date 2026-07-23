from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("commissions", "0049_compensationplan_governance_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_name",
            field=models.CharField(
                blank=True,
                help_text="Customer / account name for the transaction.",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="source",
            field=models.CharField(
                blank=True,
                default="manual",
                help_text="Origin: manual, csv, crm, imported.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="sales_credits",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Credit split rows: [{employee_id, name, role, percent}].",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
