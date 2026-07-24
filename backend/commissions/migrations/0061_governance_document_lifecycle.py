from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0060_compensation_document_repository"),
    ]

    operations = [
        migrations.AddField(
            model_name="compensationdocument",
            name="business_unit",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AlterField(
            model_name="compensationdocument",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending_review", "Pending Review"),
                    ("approved", "Approved"),
                    ("active", "Active"),
                    ("expired", "Expired"),
                    ("archived", "Archived"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
    ]
