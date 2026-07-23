"""Phase 1.3 authentication hardening tests."""

import pyotp
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.authtoken.models import Token

from .auth_hardening import (
    apply_password_update,
    password_in_history,
    start_totp_enrollment,
    confirm_totp_enrollment,
)
from .credential_crypto import encrypt_value
from .models import LoginEvent, Organization, UserMfaDevice, UserProfile
from .tenants import get_default_organization


@override_settings(
    DEBUG=True,
    CREDENTIALS_ENCRYPTION_KEY="test-auth-hardening-key",
    TOKEN_TTL_MINUTES=60,
)
class AuthHardeningTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.org.password_history_count = 3
        self.org.password_max_age_days = 0
        self.org.alert_on_new_login_ip = True
        self.org.require_mfa = False
        self.org.save()
        self.user = User.objects.create_user(
            username="auth-user", email="auth-user@test.com", password="OldPass123!"
        )
        self.profile = UserProfile.objects.create(
            organization=self.org,
            employee_id="AUTH-1",
            email="auth-user@test.com",
            name="Auth User",
            role="Admin",
            position_name="Admin",
            password_changed_at=timezone.now(),
        )
        self.client = Client()

    def _login(self, password="OldPass123!", **extra):
        return self.client.post(
            "/api/auth/email-login/",
            {"email": "auth-user@test.com", "password": password, **extra},
            content_type="application/json",
        )

    def test_login_creates_login_event_and_session(self):
        res = self._login()
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())
        self.assertTrue(
            LoginEvent.objects.filter(
                user=self.user, outcome=LoginEvent.OUTCOME_SUCCESS
            ).exists()
        )

    def test_password_history_blocks_reuse(self):
        apply_password_update(self.user, "NewPass123!", organization=self.org)
        self.assertTrue(password_in_history(self.user, "OldPass123!"))
        self.assertTrue(password_in_history(self.user, "NewPass123!"))

        token = Token.objects.create(user=self.user)
        res = self.client.post(
            "/api/auth/change-password/",
            {"old_password": "NewPass123!", "new_password": "OldPass123!"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("recently used", res.json().get("error", "").lower())

    def test_password_expiry_forces_change_flag(self):
        self.org.password_max_age_days = 30
        self.org.save()
        self.profile.password_changed_at = timezone.now() - timedelta(days=45)
        self.profile.save(update_fields=["password_changed_at"])
        res = self._login()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("must_change_password"))

    def test_mfa_challenge_and_verify(self):
        device, secret, _uri = start_totp_enrollment(self.user)
        self.assertTrue(confirm_totp_enrollment(self.user, device.id, pyotp.TOTP(secret).now()))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.mfa_enabled)

        res = self._login(device_id="device-abc")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("mfa_required"))
        mfa_token = res.json()["mfa_token"]
        code = pyotp.TOTP(secret).now()
        verify = self.client.post(
            "/api/auth/mfa/verify/",
            {
                "mfa_token": mfa_token,
                "code": code,
                "device_id": "device-abc",
                "remember_device": True,
            },
            content_type="application/json",
        )
        self.assertEqual(verify.status_code, 200)
        self.assertIn("token", verify.json())

    def test_trusted_device_skips_mfa(self):
        device, secret, _uri = start_totp_enrollment(self.user)
        confirm_totp_enrollment(self.user, device.id, pyotp.TOTP(secret).now())
        # First login with MFA + remember
        res = self._login(device_id="trusted-1", remember_device=True)
        mfa_token = res.json()["mfa_token"]
        self.client.post(
            "/api/auth/mfa/verify/",
            {
                "mfa_token": mfa_token,
                "code": pyotp.TOTP(secret).now(),
                "device_id": "trusted-1",
                "remember_device": True,
            },
            content_type="application/json",
        )
        # Second login on same device skips MFA
        res2 = self._login(device_id="trusted-1")
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.json().get("mfa_required"))
        self.assertIn("token", res2.json())

    def test_login_history_endpoint(self):
        login = self._login()
        token = login.json()["token"]
        hist = self.client.get(
            "/api/auth/login-history/",
            HTTP_AUTHORIZATION=f"Token {token}",
        )
        self.assertEqual(hist.status_code, 200)
        self.assertGreaterEqual(len(hist.json().get("results") or []), 1)

    def test_suspicious_new_ip_flagged(self):
        # Seed a prior success from a different IP
        LoginEvent.objects.create(
            organization=self.org,
            user=self.user,
            email=self.user.email,
            outcome=LoginEvent.OUTCOME_SUCCESS,
            ip_address="10.0.0.1",
        )
        res = self._login()
        self.assertEqual(res.status_code, 200)
        # Client test IP is typically 127.0.0.1
        event = LoginEvent.objects.filter(
            user=self.user, outcome=LoginEvent.OUTCOME_SUCCESS
        ).order_by("-created_at").first()
        self.assertTrue(event.suspicious)
        self.assertEqual(event.suspicion_reason, "new_ip_address")
