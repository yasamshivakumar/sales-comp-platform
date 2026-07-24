import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("commissions", "0061_governance_document_lifecycle"),
    ]

    operations = [
        migrations.AddField(
            model_name="compensationdocument",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not started"),
                    ("pending", "Pending"),
                    ("in_review", "In review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="not_started",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_compensation_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_compensation_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_compensation_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="last_activity_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="compensationdocument",
            name="linked_rules",
            field=models.ManyToManyField(
                blank=True,
                related_name="supporting_documents",
                to="commissions.commissionrule",
            ),
        ),
        migrations.AlterField(
            model_name="compensationdocument",
            name="approval_required",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="compensationdocument",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_review", "Pending Review"),
                    ("approved", "Approved"),
                    ("published", "Published"),
                    ("expired", "Expired"),
                    ("archived", "Archived"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
    ]
