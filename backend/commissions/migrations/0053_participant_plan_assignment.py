import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0052_people_enterprise_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="assigned_compensation_plan",
            field=models.ForeignKey(
                blank=True,
                help_text="Explicit compensation plan assignment for this participant.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_participants",
                to="commissions.compensationplan",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="comp_effective_date",
            field=models.DateField(
                blank=True,
                help_text="Effective date for compensation plan / quota assignment.",
                null=True,
            ),
        ),
    ]
