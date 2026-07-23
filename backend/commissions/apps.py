import sys

from django.apps import AppConfig


def _skip_encryption_startup_check() -> bool:
    """Skip during build-only management commands (Render collectstatic, etc.)."""
    argv = " ".join(sys.argv).lower()
    skip_tokens = (
        "collectstatic",
        "makemigrations",
        "migrate",
        "showmigrations",
        "check",
    )
    return any(token in argv for token in skip_tokens)


class CommissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "commissions"

    def ready(self):
        # Validate CRM encryption when the web process boots (gunicorn / runserver).
        # Skip during collectstatic/migrate so Render builds and DB migrate can run
        # before CREDENTIALS_ENCRYPTION_KEY is present.
        if _skip_encryption_startup_check():
            return

        from django.conf import settings

        from .credential_crypto import validate_encryption_ready

        validate_encryption_ready(strict=not settings.DEBUG)
