"""Phase 1.1–1.2 credential encryption and secret manager tests."""

from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from rest_framework.authtoken.models import Token

from .audit import record_audit
from .credential_crypto import (
    CredentialEncryptionError,
    credentials_blob_decrypt,
    credentials_blob_encrypt,
    decrypt_value,
    encrypt_value,
    mask_credentials,
    public_credential_metadata,
    redact_secrets,
    seal_credentials,
    unseal_credentials,
    validate_encryption_ready,
)
from .models import AuditLog, ExternalIntegration, UserProfile
from .secrets import get_secret_manager
from .tenants import get_default_organization


@override_settings(
    DEBUG=True,
    CREDENTIALS_ENCRYPTION_KEY="test-credentials-key-phase1",
    CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS=[],
    SECRET_MANAGER_BACKEND="encrypted_db",
)
class CredentialSecretsTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.admin = User.objects.create_user(
            username="sec-admin", email="sec-admin@test.com", password="pass"
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="ADM-SEC",
            email="sec-admin@test.com",
            name="Admin",
            role="Admin",
            position_name="Admin",
        )
        self.client = Client()
        self.auth = {
            "HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=self.admin).key}"
        }

    def test_validate_encryption_ready_prod_requires_key(self):
        with override_settings(DEBUG=False, CREDENTIALS_ENCRYPTION_KEY=""):
            with self.assertRaises(ImproperlyConfigured):
                validate_encryption_ready(strict=True)

    def test_blob_roundtrip_and_metadata_strip(self):
        creds = {
            "access_token": "pat-secret",
            "instance_url": "https://crm.example",
            "client_id": "cid",
        }
        blob = credentials_blob_encrypt(creds)
        self.assertTrue(blob.startswith("enc:v1:"))
        opened = credentials_blob_decrypt(blob)
        self.assertEqual(opened["access_token"], "pat-secret")
        self.assertEqual(opened["instance_url"], "https://crm.example")
        meta = public_credential_metadata(creds)
        self.assertNotIn("access_token", meta)
        self.assertEqual(meta["instance_url"], "https://crm.example")

    def test_secret_manager_encrypt_decrypt(self):
        manager = get_secret_manager()
        blob = manager.encrypt_credentials({"access_token": "tok-1", "region": "na1"})
        data = manager.decrypt_credentials(blob)
        self.assertEqual(data["access_token"], "tok-1")
        rotated = manager.rotate(blob)
        self.assertTrue(rotated.startswith("enc:v1:"))
        self.assertEqual(manager.decrypt_credentials(rotated)["access_token"], "tok-1")

    def test_integration_never_stores_plaintext_secrets(self):
        integration = ExternalIntegration.objects.create(
            organization=self.org,
            name="Secure CRM",
            provider=ExternalIntegration.PROVIDER_HUBSPOT,
            created_by=self.admin,
        )
        integration.set_encrypted_credentials(
            {"access_token": "pat-live-secret", "portal_id": "123"}
        )
        integration.save()
        integration.refresh_from_db()
        self.assertTrue(integration.encrypted_credentials.startswith("enc:v1:"))
        self.assertNotIn("access_token", integration.credentials or {})
        self.assertNotIn("pat-live-secret", str(integration.credentials))
        self.assertEqual(
            integration.get_decrypted_credentials()["access_token"], "pat-live-secret"
        )

    def test_api_never_leaks_secrets_or_ciphertext(self):
        create = self.client.post(
            "/api/integrations/center/wizard/",
            {
                "provider": "hubspot",
                "name": "Masked CRM",
                "auth_method": "token",
                "credentials": {"access_token": "pat-must-not-leak"},
                "objects_enabled": {"users": True, "deals": True},
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(create.status_code, 201)
        body = create.json()
        self.assertNotIn("pat-must-not-leak", str(body))
        self.assertNotIn("encrypted_credentials", body)
        self.assertNotIn("credentials", body)
        masked = body.get("credentials_masked") or {}
        self.assertEqual(masked.get("access_token"), "••••••••")

        integration_id = body["id"]
        detail = self.client.get(f"/api/integrations/{integration_id}/", **self.auth)
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertNotIn("encrypted_credentials", payload)
        self.assertNotIn("credentials", payload)
        self.assertNotIn("pat-must-not-leak", str(payload))
        self.assertEqual(
            (payload.get("credentials_masked") or {}).get("access_token"), "••••••••"
        )

    def test_audit_redacts_secrets(self):
        class DummyRequest:
            user = self.admin
            organization = self.org
            META = {}
            request_id = "test-req"

        record_audit(
            DummyRequest(),
            "integration_test",
            detail={"access_token": "should-redact", "name": "ok"},
            organization=self.org,
            user=self.admin,
        )
        row = AuditLog.objects.filter(action="integration_test").latest("created_at")
        self.assertEqual(row.detail.get("access_token"), "••••••••")
        self.assertEqual(row.detail.get("name"), "ok")

    def test_reencrypt_command_migrates_legacy_plaintext(self):
        integration = ExternalIntegration.objects.create(
            organization=self.org,
            name="Legacy CRM",
            provider=ExternalIntegration.PROVIDER_HUBSPOT,
            credentials={"access_token": "legacy-plain", "instance_url": "https://x"},
            encrypted_credentials="",
            created_by=self.admin,
        )
        out = StringIO()
        call_command("reencrypt_integration_credentials", stdout=out)
        integration.refresh_from_db()
        self.assertTrue(integration.encrypted_credentials.startswith("enc:v1:"))
        self.assertNotIn("access_token", integration.credentials or {})
        self.assertEqual(
            integration.get_decrypted_credentials()["access_token"], "legacy-plain"
        )

    def test_rotation_with_previous_key(self):
        old_key = "old-rotation-key-aaaa"
        new_key = "new-rotation-key-bbbb"
        with override_settings(
            CREDENTIALS_ENCRYPTION_KEY=old_key,
            CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS=[],
        ):
            sealed = encrypt_value("rotate-me")
            self.assertTrue(sealed.startswith("enc:v1:"))

        with override_settings(
            CREDENTIALS_ENCRYPTION_KEY=new_key,
            CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS=[old_key],
        ):
            self.assertEqual(decrypt_value(sealed), "rotate-me")
            resealed = encrypt_value("rotate-me")
            self.assertNotEqual(resealed, sealed)
            self.assertEqual(decrypt_value(resealed), "rotate-me")

        with override_settings(
            CREDENTIALS_ENCRYPTION_KEY=new_key,
            CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS=[],
        ):
            with self.assertRaises(CredentialEncryptionError):
                decrypt_value(sealed)

    def test_redact_secrets_nested(self):
        payload = redact_secrets(
            {"outer": {"access_token": "x", "ok": 1}, "credentials": {"a": 1}}
        )
        self.assertEqual(payload["outer"]["access_token"], "••••••••")
        self.assertEqual(payload["outer"]["ok"], 1)
        self.assertEqual(payload["credentials"], "••••••••")


@override_settings(
    DEBUG=True,
    CREDENTIALS_ENCRYPTION_KEY="test-credentials-key-phase1",
    SECRET_MANAGER_BACKEND="encrypted_db",
)
class LegacySealCompatibilityTests(TestCase):
    def test_seal_unseal_mask_still_work(self):
        sealed = seal_credentials(
            {"access_token": "secret-token", "instance_url": "https://x.example"}
        )
        self.assertTrue(str(sealed["access_token"]).startswith("enc:v1:"))
        opened = unseal_credentials(sealed)
        self.assertEqual(opened["access_token"], "secret-token")
        masked = mask_credentials(opened)
        self.assertEqual(masked["access_token"], "••••••••")
