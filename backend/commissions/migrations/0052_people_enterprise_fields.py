from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0051_userprofile_people_access_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userinvite",
            name="opened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="custom_permissions",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Optional permission code overrides for custom roles.",
            ),
        ),
    ]
