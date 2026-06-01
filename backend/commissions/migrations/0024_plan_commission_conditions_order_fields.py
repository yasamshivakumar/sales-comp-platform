# Generated manually for plan commission conditions

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0023_delete_incentiverule"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="region",
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="product_name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_segment",
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="business_group",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.CreateModel(
            name="PlanCommissionCondition",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "field",
                    models.CharField(
                        choices=[
                            ("region", "Region"),
                            ("product_name", "Product"),
                            ("service_name", "Service"),
                            ("customer_segment", "Customer Segment"),
                            ("business_group", "Business Group"),
                            ("order_status", "Order Status"),
                            ("currency", "Currency"),
                            ("position_name", "Position Name"),
                            ("employee_id", "Employee ID"),
                            ("sales_amount", "Sales Amount"),
                        ],
                        max_length=50,
                    ),
                ),
                (
                    "operator",
                    models.CharField(
                        choices=[
                            ("eq", "Equals"),
                            ("neq", "Not equals"),
                            ("in", "In list (comma-separated)"),
                            ("contains", "Contains"),
                            ("gt", "Greater than"),
                            ("gte", "Greater or equal"),
                            ("lt", "Less than"),
                            ("lte", "Less or equal"),
                            ("empty", "Is empty"),
                            ("not_empty", "Is not empty"),
                        ],
                        default="eq",
                        max_length=20,
                    ),
                ),
                (
                    "value",
                    models.CharField(
                        blank=True,
                        help_text="Comparison value, or comma-separated list for 'In list'.",
                        max_length=500,
                    ),
                ),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "compensation_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_conditions",
                        to="commissions.compensationplan",
                    ),
                ),
            ],
            options={
                "ordering": ["sequence", "id"],
            },
        ),
    ]
