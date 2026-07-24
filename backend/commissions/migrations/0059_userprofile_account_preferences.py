from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0058_report_builder"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="account_preferences",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Personal prefs: timezone, language, notifications, ui.",
            ),
        ),
    ]
