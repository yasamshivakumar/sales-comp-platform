from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0024_plan_commission_conditions_order_fields"),
    ]

    operations = [
        migrations.DeleteModel(
            name="PlanCommissionCondition",
        ),
        migrations.RemoveField(
            model_name="order",
            name="region",
        ),
        migrations.RemoveField(
            model_name="order",
            name="product_name",
        ),
        migrations.RemoveField(
            model_name="order",
            name="customer_segment",
        ),
        migrations.RemoveField(
            model_name="order",
            name="business_group",
        ),
    ]
