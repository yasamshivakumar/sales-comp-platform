from django.apps import AppConfig


class CommissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "commissions"

    def ready(self):
        # Validate CRM encryption configuration once the app registry is loaded.
        from django.conf import settings

        from .credential_crypto import validate_encryption_ready

        validate_encryption_ready(strict=not settings.DEBUG)
