from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0031_dispute_employee_acknowledgment"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="distribution",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Distribution channel (used by SC Lookup Table matching)",
                max_length=200,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="compensationplan",
            name="commission_table_type",
            field=models.CharField(
                choices=[
                    ("RATE", "SC Rate Table"),
                    ("FLAT", "SC Flat Rate Table"),
                    ("LOOKUP", "SC Lookup Table"),
                ],
                default="RATE",
                help_text="Select which commission table type this plan uses.",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="SCLookupTable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tier_name", models.CharField(blank=True, default="", max_length=100)),
                (
                    "product_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Leave blank to match any product",
                        max_length=200,
                    ),
                ),
                (
                    "service_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Leave blank to match any service",
                        max_length=200,
                    ),
                ),
                (
                    "distribution",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Leave blank to match any distribution channel",
                        max_length=200,
                    ),
                ),
                ("from_amount", models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                (
                    "to_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Leave blank for no upper limit",
                        max_digits=15,
                        null=True,
                    ),
                ),
                (
                    "commission_rate",
                    models.DecimalField(
                        decimal_places=4,
                        help_text="Percentage value. Example: 5.00 = 5%",
                        max_digits=8,
                    ),
                ),
                ("bonus_amount", models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "compensation_plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sc_lookup_tables",
                        to="commissions.compensationplan",
                    ),
                ),
            ],
            options={
                "ordering": ["sequence", "id"],
            },
        ),
    ]
