"""Backfill: every existing CompensationPlan becomes Version 1.

- Active plans   -> Published version 1 (immutable going forward)
- Draft plans    -> Draft version 1 (still editable)
- Inactive plans -> Archived version 1 (read-only history)

Existing rate tables, lookup rows, and commission rules are linked to
version 1. Historical commissions are linked to their plan's version 1 so
payouts reference the exact version forever. No amounts are recalculated.
"""
from django.db import migrations
from django.utils import timezone


def backfill_versions(apps, schema_editor):
    CompensationPlan = apps.get_model("commissions", "CompensationPlan")
    CommissionPlanVersion = apps.get_model("commissions", "CommissionPlanVersion")
    SCRateTable = apps.get_model("commissions", "SCRateTable")
    SCFlatRateTable = apps.get_model("commissions", "SCFlatRateTable")
    SCLookupTable = apps.get_model("commissions", "SCLookupTable")
    CommissionRule = apps.get_model("commissions", "CommissionRule")
    Commission = apps.get_model("commissions", "Commission")

    status_map = {
        "Active": "Published",
        "Draft": "Draft",
        "Inactive": "Archived",
    }

    now = timezone.now()

    for plan in CompensationPlan.objects.all().iterator():
        if CommissionPlanVersion.objects.filter(compensation_plan=plan).exists():
            continue

        version_status = status_map.get(plan.status, "Published")
        version = CommissionPlanVersion.objects.create(
            organization_id=plan.organization_id,
            compensation_plan=plan,
            version_number=1,
            status=version_status,
            effective_from=plan.effective_start_date,
            effective_to=plan.effective_end_date,
            published_at=now if version_status == "Published" else None,
            description="Migrated from existing compensation plan.",
            pay_period_type=plan.pay_period_type,
            plan_basis=plan.plan_basis,
            commission_table_type=plan.commission_table_type,
            position_name=plan.position_name,
            role=plan.role,
            territory_id=plan.territory_id,
            title=plan.title,
            business_group=plan.business_group,
        )

        SCRateTable.objects.filter(
            compensation_plan=plan, plan_version__isnull=True
        ).update(plan_version=version)
        SCFlatRateTable.objects.filter(
            compensation_plan=plan, plan_version__isnull=True
        ).update(plan_version=version)
        SCLookupTable.objects.filter(
            compensation_plan=plan, plan_version__isnull=True
        ).update(plan_version=version)
        CommissionRule.objects.filter(
            compensation_plan=plan, plan_version__isnull=True
        ).update(plan_version=version)
        Commission.objects.filter(
            compensation_plan=plan, plan_version__isnull=True
        ).update(plan_version=version)


def unlink_versions(apps, schema_editor):
    """Reverse: detach FKs and drop backfilled versions (schema migration
    reversal removes the columns/tables)."""
    CommissionPlanVersion = apps.get_model("commissions", "CommissionPlanVersion")
    Commission = apps.get_model("commissions", "Commission")

    Commission.objects.filter(plan_version__isnull=False).update(plan_version=None)
    CommissionPlanVersion.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0043_commission_plan_versioning"),
    ]

    operations = [
        migrations.RunPython(backfill_versions, unlink_versions),
    ]
