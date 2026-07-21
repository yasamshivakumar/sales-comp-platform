from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0045_restore_crm_user_id_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="compensationplan",
            name="tier_calculation_method",
            field=models.CharField(
                choices=[
                    ("flat", "Flat (whole amount at the landing tier rate)"),
                    ("marginal", "Marginal (each slice at its own tier rate)"),
                ],
                default="flat",
                help_text=(
                    "Flat applies the landing tier rate to the whole amount. "
                    "Marginal applies each tier rate only to the portion of "
                    "sales that falls within that tier (like tax brackets)."
                ),
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="commissionplanversion",
            name="tier_calculation_method",
            field=models.CharField(
                choices=[
                    ("flat", "Flat (whole amount at the landing tier rate)"),
                    ("marginal", "Marginal (each slice at its own tier rate)"),
                ],
                default="flat",
                max_length=10,
            ),
        ),
    ]
