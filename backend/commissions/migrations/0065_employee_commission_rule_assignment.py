# Employee-specific commission rule assignments.
#
# Runtime evaluation is strict: only assigned rules apply. This migration
# backfills assignments for employees who already have assigned_compensation_plan
# matching each rule's plan so existing calculations are not broken.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_rule_assignments(apps, schema_editor):
    CommissionRule = apps.get_model("commissions", "CommissionRule")
    CommissionPlanVersion = apps.get_model("commissions", "CommissionPlanVersion")
    UserProfile = apps.get_model("commissions", "UserProfile")
    Assignment = apps.get_model("commissions", "EmployeeCommissionRuleAssignment")

    version_plan = {
        row["id"]: row["compensation_plan_id"]
        for row in CommissionPlanVersion.objects.values("id", "compensation_plan_id")
    }

    bulk = []
    existing = set(
        Assignment.objects.values_list("employee_id", "rule_id")
    )

    for rule in CommissionRule.objects.all().iterator():
        plan_id = rule.compensation_plan_id
        if not plan_id and rule.plan_version_id:
            plan_id = version_plan.get(rule.plan_version_id)
        if not plan_id:
            continue

        employees = UserProfile.objects.filter(assigned_compensation_plan_id=plan_id)
        if rule.organization_id:
            employees = employees.filter(organization_id=rule.organization_id)

        for emp in employees.only("id", "organization_id").iterator():
            key = (emp.id, rule.id)
            if key in existing:
                continue
            existing.add(key)
            bulk.append(
                Assignment(
                    organization_id=rule.organization_id or emp.organization_id,
                    employee_id=emp.id,
                    rule_id=rule.id,
                )
            )
            if len(bulk) >= 500:
                Assignment.objects.bulk_create(bulk, ignore_conflicts=True)
                bulk = []

    if bulk:
        Assignment.objects.bulk_create(bulk, ignore_conflicts=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("commissions", "0064_alter_commissionrule_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeeCommissionRuleAssignment",
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
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="commission_rule_assignments_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_rule_assignments",
                        to="commissions.userprofile",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commission_rule_assignments",
                        to="commissions.organization",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="employee_assignments",
                        to="commissions.commissionrule",
                    ),
                ),
            ],
            options={
                "ordering": ["-assigned_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="commissionrule",
            name="assigned_employees",
            field=models.ManyToManyField(
                blank=True,
                related_name="assigned_commission_rules",
                through="commissions.EmployeeCommissionRuleAssignment",
                to="commissions.userprofile",
            ),
        ),
        migrations.AddIndex(
            model_name="employeecommissionruleassignment",
            index=models.Index(
                fields=["employee", "rule"], name="emprule_emp_rule_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="employeecommissionruleassignment",
            index=models.Index(
                fields=["organization", "rule"], name="emprule_org_rule_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="employeecommissionruleassignment",
            constraint=models.UniqueConstraint(
                fields=("employee", "rule"), name="uniq_employee_commission_rule"
            ),
        ),
        migrations.RunPython(backfill_rule_assignments, noop_reverse),
    ]
