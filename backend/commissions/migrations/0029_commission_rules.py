# Generated manually for Xactly-style commission rules

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0028_monthly_compensation_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="product_name",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="region",
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
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
            name="CommissionRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "rule_type",
                    models.CharField(
                        choices=[
                            ("commission_flat", "Commission - Flat Rate"),
                            ("commission_rate", "Commission - Rate"),
                            ("credit_amount", "Credit - Amount"),
                            ("credit_percent", "Credit - Percentage"),
                            ("multiplier", "Multiplier"),
                        ],
                        default="commission_rate",
                        max_length=32,
                    ),
                ),
                ("multiplier", models.DecimalField(decimal_places=4, default=1, max_digits=12)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("version_label", models.CharField(blank=True, default="Start of Time - End of Time", max_length=255)),
                ("effective_start_date", models.DateField(blank=True, null=True)),
                ("effective_end_date", models.DateField(blank=True, null=True)),
                ("active_start_date", models.DateField(blank=True, null=True)),
                ("active_end_date", models.DateField(blank=True, null=True)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("stop_on_match", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "compensation_plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_rules",
                        to="commissions.compensationplan",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_rules",
                        to="commissions.organization",
                    ),
                ),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
        migrations.CreateModel(
            name="CommissionRuleCondition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
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
                            ("territory_code", "Territory Code"),
                            ("role", "Role"),
                            ("plan_basis", "Plan Basis"),
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
                            ("in", "In list"),
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
                ("value", models.CharField(blank=True, default="", max_length=500)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conditions",
                        to="commissions.commissionrule",
                    ),
                ),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
        migrations.CreateModel(
            name="CommissionRuleResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("result_name", models.CharField(default="Result", max_length=255)),
                (
                    "hold_period",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("30_days", "30 Days"),
                            ("60_days", "60 Days"),
                            ("90_days", "90 Days"),
                            ("until_paid", "Until Paid"),
                        ],
                        default="none",
                        max_length=32,
                    ),
                ),
                (
                    "result_classification",
                    models.CharField(
                        choices=[
                            ("commission", "Commission"),
                            ("credit", "Credit"),
                            ("bonus", "Bonus"),
                            ("spiff", "SPIFF"),
                            ("draw", "Draw"),
                            ("override", "Override"),
                        ],
                        default="commission",
                        max_length=32,
                    ),
                ),
                ("quota_enabled", models.BooleanField(default=False)),
                (
                    "quota_period",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("monthly", "Monthly"),
                            ("quarterly", "Quarterly"),
                            ("annual", "Annual"),
                        ],
                        default="",
                        max_length=32,
                    ),
                ),
                (
                    "result_rate_type",
                    models.CharField(
                        choices=[
                            ("flat_amount", "Flat Amount"),
                            ("percentage", "Percentage"),
                            ("multiplier", "Multiplier"),
                            ("override", "Override Amount"),
                            ("add_bonus", "Add Bonus"),
                        ],
                        default="percentage",
                        max_length=32,
                    ),
                ),
                ("rate_value", models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ("minimum_value", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ("maximum_value", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                (
                    "earning_group",
                    models.CharField(
                        choices=[
                            ("base", "Base Commission"),
                            ("bonus", "Bonus"),
                            ("spiff", "SPIFF"),
                            ("adjustment", "Adjustment"),
                        ],
                        default="base",
                        max_length=32,
                    ),
                ),
                (
                    "value_unit_type",
                    models.CharField(
                        choices=[
                            ("currency", "Currency"),
                            ("percent", "Percent"),
                            ("units", "Units"),
                            ("quota_pct", "Percent of Quota"),
                        ],
                        default="currency",
                        max_length=32,
                    ),
                ),
                ("reason_code", models.CharField(blank=True, default="", max_length=100)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="commissions.commissionrule",
                    ),
                ),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
        migrations.AddField(
            model_name="commission",
            name="commission_rule",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="commissions",
                to="commissions.commissionrule",
            ),
        ),
        migrations.AddField(
            model_name="commission",
            name="credit_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name="commission",
            name="result_classification",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="commission",
            name="earning_group",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="commission",
            name="hold_until",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="commission",
            name="reason_code",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="commission",
            name="rule_result_name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
