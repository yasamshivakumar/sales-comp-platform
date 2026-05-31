from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0017_remove_compensationplan_is_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="order",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sale_record",
                to="commissions.order",
            ),
        ),
    ]
