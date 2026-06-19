from django.db import migrations, models
import django.db.models.deletion


def backfill_ledger_organizations(apps, schema_editor):
    Organization = apps.get_model("commissions", "Organization")
    UserProfile = apps.get_model("commissions", "UserProfile")
    Employee = apps.get_model("commissions", "Employee")
    Sale = apps.get_model("commissions", "Sale")
    Commission = apps.get_model("commissions", "Commission")

    default_org, _ = Organization.objects.get_or_create(
        slug="default",
        defaults={"name": "Default Organization"},
    )

    for sale in Sale.objects.select_related("order").all().iterator():
        org_id = getattr(sale.order, "organization_id", None) if sale.order_id else None
        sale.organization_id = org_id or default_org.id
        sale.save(update_fields=["organization"])

    for employee in Employee.objects.all().iterator():
        profile = (
            UserProfile.objects.filter(email__iexact=employee.email)
            .exclude(organization__isnull=True)
            .first()
        )
        if profile:
            employee.organization_id = profile.organization_id
        else:
            sale = (
                Sale.objects.filter(employee_id=employee.id)
                .exclude(organization__isnull=True)
                .first()
            )
            employee.organization_id = sale.organization_id if sale else default_org.id
        employee.save(update_fields=["organization"])

    for commission in Commission.objects.select_related("sale").all().iterator():
        org_id = commission.sale.organization_id if commission.sale_id else None
        commission.organization_id = org_id or default_org.id
        commission.save(update_fields=["organization"])


class Migration(migrations.Migration):
    dependencies = [
        ("commissions", "0034_order_needs_recalculation"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="employees",
                to="commissions.organization",
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sales",
                to="commissions.organization",
            ),
        ),
        migrations.AddField(
            model_name="commission",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="commissions",
                to="commissions.organization",
            ),
        ),
        migrations.RunPython(backfill_ledger_organizations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="employee",
            name="email",
            field=models.EmailField(db_index=True, max_length=254),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                fields=("organization", "email"),
                name="uniq_employee_email_per_org",
            ),
        ),
        migrations.AddIndex(
            model_name="commission",
            index=models.Index(
                fields=["organization", "status", "calculated_at"],
                name="commission_org_status_calc_idx",
            ),
        ),
    ]
