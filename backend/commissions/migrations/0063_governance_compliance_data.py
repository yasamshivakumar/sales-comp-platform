from django.db import migrations


def migrate_active_to_published(apps, schema_editor):
    CompensationDocument = apps.get_model("commissions", "CompensationDocument")
    CompensationDocument.objects.filter(status="active").update(status="published")


def reverse_published_to_active(apps, schema_editor):
    CompensationDocument = apps.get_model("commissions", "CompensationDocument")
    CompensationDocument.objects.filter(status="published").update(status="active")


def backfill_created_by(apps, schema_editor):
    CompensationDocument = apps.get_model("commissions", "CompensationDocument")
    for doc in CompensationDocument.objects.filter(created_by__isnull=True).exclude(
        uploaded_by__isnull=True
    ):
        doc.created_by_id = doc.uploaded_by_id
        doc.last_activity_at = doc.updated_at or doc.created_at
        doc.save(update_fields=["created_by_id", "last_activity_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0062_governance_compliance_workflow"),
    ]

    operations = [
        migrations.RunPython(migrate_active_to_published, reverse_published_to_active),
        migrations.RunPython(backfill_created_by, migrations.RunPython.noop),
    ]
