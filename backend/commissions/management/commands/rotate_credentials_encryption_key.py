"""Rotate Fernet key material for stored CRM credentials.

Usage:
  1. Set CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS to the old key(s).
  2. Set CREDENTIALS_ENCRYPTION_KEY to the new key.
  3. Run: python manage.py rotate_credentials_encryption_key
"""

from django.core.management.base import BaseCommand, CommandError

from commissions.credential_crypto import CredentialEncryptionError
from commissions.models import ExternalIntegration
from commissions.secrets import get_secret_manager


class Command(BaseCommand):
    help = (
        "Re-seal all encrypted CRM credentials under the current "
        "CREDENTIALS_ENCRYPTION_KEY (decrypting with previous keys as needed)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        manager = get_secret_manager()
        qs = ExternalIntegration.objects.all().order_by("id")
        updated = 0
        failed = 0

        for integration in qs.iterator():
            try:
                new_blob = manager.rotate(
                    integration.encrypted_credentials or None,
                    legacy_credentials=integration.credentials or {},
                )
            except CredentialEncryptionError as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"id={integration.pk} rotate failed: {exc}")
                )
                continue
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"id={integration.pk} rotate failed: {exc}")
                )
                continue

            if dry_run:
                updated += 1
                continue

            integration.encrypted_credentials = new_blob
            # Keep metadata-only JSON (set_encrypted_credentials also strips secrets).
            from commissions.credential_crypto import public_credential_metadata

            plaintext = manager.decrypt_credentials(new_blob, legacy_credentials={})
            integration.credentials = public_credential_metadata(plaintext)
            integration.save(
                update_fields=["credentials", "encrypted_credentials", "updated_at"]
            )
            updated += 1
            self.stdout.write(self.style.SUCCESS(f"Rotated id={integration.pk}"))

        self.stdout.write(f"Done. updated={updated} failed={failed} dry_run={dry_run}")
        if failed:
            raise CommandError(f"{failed} integration(s) failed to rotate")
