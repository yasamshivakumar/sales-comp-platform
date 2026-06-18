"""Normalize existing plans to single-calendar-month effective windows."""

import calendar
from datetime import date

from django.db import migrations


def snap_plans_to_month(apps, schema_editor):
    CompensationPlan = apps.get_model("commissions", "CompensationPlan")
    for plan in CompensationPlan.objects.all().iterator():
        start = plan.effective_start_date
        if not start:
            continue
        last_day = calendar.monthrange(start.year, start.month)[1]
        plan.effective_end_date = date(start.year, start.month, last_day)
        plan.pay_period_type = plan.pay_period_type or "Monthly"
        plan.save(update_fields=["effective_end_date", "pay_period_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0027_external_integrations"),
    ]

    operations = [
        migrations.RunPython(snap_plans_to_month, migrations.RunPython.noop),
    ]
