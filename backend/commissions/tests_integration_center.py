"""CRM Integration Center API tests."""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from .credential_crypto import mask_credentials, seal_credentials, unseal_credentials
from .models import CRMFieldMapping, ExternalIntegration, UserProfile
from .tenants import get_default_organization


class IntegrationCenterTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.admin = User.objects.create_user(
            username="ic-admin", email="ic-admin@test.com", password="pass"
        )
        self.rep = User.objects.create_user(
            username="ic-rep", email="ic-rep@test.com", password="pass"
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="ADM-IC",
            email="ic-admin@test.com",
            name="Admin",
            role="Admin",
            position_name="Admin",
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="REP-IC",
            email="ic-rep@test.com",
            name="Rep",
            role="Sales",
            position_name="Sales Rep",
        )
        self.client = Client()
        self.admin_auth = {
            "HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=self.admin).key}"
        }
        self.rep_auth = {
            "HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=self.rep).key}"
        }

    def test_credential_seal_roundtrip(self):
        sealed = seal_credentials({"access_token": "secret-token", "instance_url": "https://x.example"})
        self.assertTrue(str(sealed["access_token"]).startswith("enc:v1:"))
        self.assertEqual(sealed["instance_url"], "https://x.example")
        opened = unseal_credentials(sealed)
        self.assertEqual(opened["access_token"], "secret-token")
        masked = mask_credentials(opened)
        self.assertEqual(masked["access_token"], "••••••••")

    def test_rep_cannot_access_center(self):
        res = self.client.get("/api/integrations/center/summary/", **self.rep_auth)
        self.assertEqual(res.status_code, 403)

    def test_admin_summary_and_wizard(self):
        summary = self.client.get("/api/integrations/center/summary/", **self.admin_auth)
        self.assertEqual(summary.status_code, 200)
        self.assertIn("kpis", summary.json())

        create = self.client.post(
            "/api/integrations/center/wizard/",
            {
                "provider": "hubspot",
                "name": "HubSpot Test",
                "auth_method": "token",
                "credentials": {"access_token": "pat-test-token"},
                "connected_org_name": "Demo Org",
                "objects_enabled": {"users": True, "deals": True},
                "sync_frequency": "daily",
            },
            content_type="application/json",
            **self.admin_auth,
        )
        self.assertEqual(create.status_code, 201)
        body = create.json()
        self.assertEqual(body["provider"], "hubspot")
        self.assertNotIn("pat-test-token", str(body))

        integration = ExternalIntegration.objects.get(pk=body["id"])
        decrypted = integration.get_decrypted_credentials()
        self.assertEqual(decrypted.get("access_token"), "pat-test-token")
        self.assertTrue(CRMFieldMapping.objects.filter(connection=integration).exists())

        # Secrets stay masked on classic retrieve
        detail = self.client.get(f"/api/integrations/{integration.id}/", **self.admin_auth)
        self.assertEqual(detail.status_code, 200)
        masked = detail.json().get("credentials_masked") or {}
        self.assertEqual(masked.get("access_token"), "••••••••")
