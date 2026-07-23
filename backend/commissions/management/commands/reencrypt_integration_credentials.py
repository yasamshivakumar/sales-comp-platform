"""Re-encrypt CRM integration credentials into Fernet blobs.

Migrates legacy plaintext / field-sealed JSON into encrypted_credentials and
strips secrets from the credentials JSON column.
"""

from django.core.management.base import BaseCommand, CommandError

from commissions.credential_crypto import SECRET_KEYS, CredentialEncryptionError
from commissions.models import ExternalIntegration
from commissions.secrets import get_secret_manager


class Command(BaseCommand):
    help = (
        "Re-encrypt all ExternalIntegration credentials with the current "
        "CREDENTIALS_ENCRYPTION_KEY and clear plaintext secrets from JSON."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        manager = get_secret_manager()
        qs = ExternalIntegration.objects.all().order_by("id")
        updated = 0
        skipped = 0
        failed = 0

        for integration in qs.iterator():
            try:
                plaintext = manager.decrypt_credentials(
                    integration.encrypted_credentials or None,
                    legacy_credentials=integration.credentials or {},
                )
            except CredentialEncryptionError as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"id={integration.pk} decrypt failed: {exc}")
                )
                continue

            has_secret = any(
                isinstance(plaintext.get(key), str) and plaintext.get(key)
                for key in SECRET_KEYS
            )
            blob_ok = bool(
                integration.encrypted_credentials
                and str(integration.encrypted_credentials).startswith("enc:v1:")
            )
            json_has_secret = any(
                key in (integration.credentials or {}) for key in SECRET_KEYS
            )

            if blob_ok and not json_has_secret and has_secret:
                skipped += 1
                continue

            if not has_secret and blob_ok and not json_has_secret:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"Would reencrypt id={integration.pk} name={integration.name!r}"
                )
                updated += 1
                continue

            try:
                integration.set_encrypted_credentials(plaintext)
                # Round-trip verify before save.
                verify = manager.decrypt_credentials(
                    integration.encrypted_credentials,
                    legacy_credentials={},
                )
                for key in SECRET_KEYS:
                    if plaintext.get(key) and verify.get(key) != plaintext.get(key):
                        raise CredentialEncryptionError(
                            f"Round-trip mismatch for key={key}"
                        )
                integration.save(
                    update_fields=["credentials", "encrypted_credentials", "updated_at"]
                )
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Reencrypted id={integration.pk}")
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"id={integration.pk} reencrypt failed: {exc}")
                )

        self.stdout.write(
            f"Done. updated={updated} skipped={skipped} failed={failed} dry_run={dry_run}"
        )
        if failed:
            raise CommandError(f"{failed} integration(s) failed to reencrypt")
