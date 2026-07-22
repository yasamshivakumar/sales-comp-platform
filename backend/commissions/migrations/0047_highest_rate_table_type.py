from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0046_tier_calculation_method"),
    ]

    operations = [
        migrations.AlterField(
            model_name="compensationplan",
            name="commission_table_type",
            field=models.CharField(
                choices=[
                    ("RATE", "SC Rate Table"),
                    ("HIGHEST", "Highest Rate Table"),
                    ("FLAT", "SC Flat Rate Table"),
                    ("LOOKUP", "SC Lookup Table"),
                ],
                default="RATE",
                help_text="Select which commission table type this plan uses.",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="commissionplanversion",
            name="commission_table_type",
            field=models.CharField(
                choices=[
                    ("RATE", "SC Rate Table"),
                    ("HIGHEST", "Highest Rate Table"),
                    ("FLAT", "SC Flat Rate Table"),
                    ("LOOKUP", "SC Lookup Table"),
                ],
                default="RATE",
                max_length=10,
            ),
        ),
    ]
