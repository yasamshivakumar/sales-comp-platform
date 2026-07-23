# Generated manually for Phase 1.3 auth hardening

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commissions", "0055_crm_integration_center"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="require_mfa",
            field=models.BooleanField(
                default=False,
                help_text="Require MFA after password login for all users in this org.",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="password_history_count",
            field=models.PositiveSmallIntegerField(
                default=5,
                help_text="Reject new passwords that match one of the last N passwords (0=off).",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="password_max_age_days",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Force password change after N days (0=disabled).",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="session_idle_minutes",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Override TOKEN_TTL_MINUTES for this org (0=use global setting).",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="max_concurrent_sessions",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Active API sessions allowed per user (platform enforces 1 DRF token).",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="remember_device_days",
            field=models.PositiveIntegerField(
                default=30,
                help_text="Days a trusted device may skip MFA.",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="alert_on_new_login_ip",
            field=models.BooleanField(
                default=True,
                help_text="Flag and audit logins from previously unseen IP addresses.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="password_changed_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last password change time (auth User).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="force_password_change",
            field=models.BooleanField(
                default=False,
                help_text="When true, API access is limited to change-password / logout.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="mfa_enabled",
            field=models.BooleanField(
                default=False,
                help_text="User has at least one confirmed MFA device.",
            ),
        ),
        migrations.CreateModel(
            name="LoginEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(blank=True, db_index=True, default="", max_length=254)),
                ("outcome", models.CharField(choices=[("success", "Success"), ("failed", "Failed"), ("locked", "Locked out"), ("mfa_required", "MFA required"), ("mfa_failed", "MFA failed")], db_index=True, max_length=20)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("device_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("suspicious", models.BooleanField(db_index=True, default=False)),
                ("suspicion_reason", models.CharField(blank=True, default="", max_length=255)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="login_events", to="commissions.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="login_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PasswordHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password_hash", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="password_history", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "verbose_name_plural": "password histories"},
        ),
        migrations.CreateModel(
            name="TrustedDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_id", models.CharField(db_index=True, max_length=64)),
                ("device_name", models.CharField(blank=True, default="", max_length=120)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("last_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("trusted_until", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="trusted_devices", to="commissions.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trusted_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UserMfaDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_type", models.CharField(choices=[("totp", "Authenticator app (TOTP)")], default="totp", max_length=20)),
                ("name", models.CharField(blank=True, default="Authenticator", max_length=100)),
                ("secret_encrypted", models.TextField()),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mfa_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="UserAuthSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(db_index=True, max_length=64, unique=True)),
                ("token_key_hash", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("device_id", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.CharField(blank=True, default="", max_length=64)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="auth_sessions", to="commissions.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="auth_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="trusteddevice",
            constraint=models.UniqueConstraint(fields=("user", "device_id"), name="uniq_trusted_device_per_user"),
        ),
    ]
