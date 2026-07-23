"""Security regression tests: tenant isolation, privilege escalation,
login lockout, logout revocation, upload limits, CSV/SSRF hardening."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from rest_framework.authtoken.models import Token

from .models import (
    Commission,
    CompensationPlan,
    CompensationTier,
    Employee,
    Order,
    Organization,
    Sale,
    UserProfile,
)
from .security import is_public_host, sanitize_csv_cell


def _make_user(email, org, role, employee_id):
    user = User.objects.create_user(username=email, email=email, password="test")
    UserProfile.objects.create(
        organization=org,
        email=email,
        username=email,
        employee_id=employee_id,
        name=email.split("@")[0],
        role=role,
        enable_login=True,
    )
    token = Token.objects.create(user=user)
    return user, Client(HTTP_AUTHORIZATION=f"Token {token.key}"), token


class TwoOrgBase(TestCase):
    def setUp(self):
        cache.clear()
        self.org_a = Organization.objects.create(slug="sec-org-a", name="Sec Org A")
        self.org_b = Organization.objects.create(slug="sec-org-b", name="Sec Org B")
        self.admin_a, self.client_admin_a, self.token_admin_a = _make_user(
            "sec-admin-a@test.com", self.org_a, "Admin", "SA1"
        )
        self.rep_a, self.client_rep_a, self.token_rep_a = _make_user(
            "sec-rep-a@test.com", self.org_a, "Sales Rep", "SR1"
        )
        self.admin_b, self.client_admin_b, self.token_admin_b = _make_user(
            "sec-admin-b@test.com", self.org_b, "Admin", "SB1"
        )
        self.emp_a = Employee.objects.create(
            organization=self.org_a, name="Emp A", email="emp-a@test.com"
        )
        self.emp_b = Employee.objects.create(
            organization=self.org_b, name="Emp B", email="emp-b@test.com"
        )


class EmployeeTenantIsolationTests(TwoOrgBase):
    def test_employee_list_is_org_scoped(self):
        res = self.client_admin_a.get("/api/employees/")
        self.assertEqual(res.status_code, 200)
        emails = {row["email"] for row in res.json()}
        self.assertIn("emp-a@test.com", emails)
        self.assertNotIn("emp-b@test.com", emails)

    def test_employee_detail_cross_org_is_404(self):
        res = self.client_admin_a.get(f"/api/employees/{self.emp_b.id}/")
        self.assertEqual(res.status_code, 404)

    def test_employee_write_requires_admin(self):
        res = self.client_rep_a.post(
            "/api/employees/",
            {"name": "Injected", "email": "inject@test.com"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)

    def test_employee_create_forces_own_org(self):
        res = self.client_admin_a.post(
            "/api/employees/",
            {
                "name": "Created",
                "email": "created@test.com",
                "organization": self.org_b.id,
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        created = Employee.objects.get(email="created@test.com")
        self.assertEqual(created.organization_id, self.org_a.id)


class UserSetupPrivilegeTests(TwoOrgBase):
    def test_list_requires_admin(self):
        res = self.client_rep_a.get("/api/user-setup/")
        self.assertEqual(res.status_code, 403)

    def test_list_is_org_scoped(self):
        res = self.client_admin_a.get("/api/user-setup/")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        rows = payload if isinstance(payload, list) else payload.get("results", [])
        emails = {row["email"] for row in rows}
        self.assertIn("sec-rep-a@test.com", emails)
        self.assertNotIn("sec-admin-b@test.com", emails)

    def test_rep_cannot_selfescalate_to_admin(self):
        res = self.client_rep_a.post(
            "/api/user-setup/",
            {"email": "sec-rep-a@test.com", "name": "Rep", "role": "Admin"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)
        profile = UserProfile.objects.get(email="sec-rep-a@test.com")
        self.assertEqual(profile.role, "Sales Rep")

    def test_rep_cannot_upload_users_csv(self):
        upload = SimpleUploadedFile(
            "users.csv",
            b"email,role\nnew@test.com,Admin\n",
            content_type="text/csv",
        )
        res = self.client_rep_a.post("/api/user-setup-upload/", {"file": upload})
        self.assertEqual(res.status_code, 403)


class CommissionWriteProtectionTests(TwoOrgBase):
    def _commission_for(self, org, employee):
        sale = Sale.objects.create(
            organization=org,
            employee=employee,
            employee_salary=Decimal("0.00"),
            amount=Decimal("10000.00"),
        )
        return Commission.objects.create(
            organization=org,
            employee=employee,
            sale=sale,
            commission_amount=Decimal("1000.00"),
        )

    def test_rep_cannot_create_commission(self):
        sale = Sale.objects.create(
            organization=self.org_a,
            employee=self.emp_a,
            employee_salary=Decimal("0.00"),
            amount=Decimal("10000.00"),
        )
        res = self.client_rep_a.post(
            "/api/commissions/",
            {
                "employee": self.emp_a.id,
                "sale": sale.id,
                "commission_amount": "99999.00",
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(Commission.objects.count(), 0)

    def test_rep_cannot_delete_own_commission(self):
        rep_employee = Employee.objects.create(
            organization=self.org_a, name="Rep A", email="sec-rep-a@test.com"
        )
        comm = self._commission_for(self.org_a, rep_employee)
        res = self.client_rep_a.delete(f"/api/commissions/{comm.id}/")
        self.assertEqual(res.status_code, 403)


class PayrollExportIsolationTests(TwoOrgBase):
    def _commission(self, org, employee):
        sale = Sale.objects.create(
            organization=org,
            employee=employee,
            employee_salary=Decimal("0.00"),
            amount=Decimal("10000.00"),
        )
        return Commission.objects.create(
            organization=org,
            employee=employee,
            sale=sale,
            commission_amount=Decimal("1000.00"),
        )

    def test_export_only_contains_own_org(self):
        self._commission(self.org_a, self.emp_a)
        self._commission(self.org_b, self.emp_b)
        res = self.client_admin_a.get("/api/commissions/export/?status=all")
        self.assertEqual(res.status_code, 200)
        body = res.content.decode("utf-8")
        self.assertIn("emp-a@test.com", body)
        self.assertNotIn("emp-b@test.com", body)

    def test_earnings_report_only_own_org(self):
        self._commission(self.org_a, self.emp_a)
        self._commission(self.org_b, self.emp_b)
        res = self.client_admin_a.get("/api/reports/employee-earnings/")
        self.assertEqual(res.status_code, 200)
        emails = {row["employee__email"] for row in res.json()["earnings"]}
        self.assertIn("emp-a@test.com", emails)
        self.assertNotIn("emp-b@test.com", emails)


class CompensationTierIsolationTests(TwoOrgBase):
    def test_cannot_attach_tier_to_other_orgs_plan(self):
        plan_b = CompensationPlan.objects.create(
            organization=self.org_b,
            plan_name="Org B Plan",
            status="Active",
            role="Sales Rep",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 12, 31),
        )
        res = self.client_admin_a.post(
            "/api/compensation-tiers/",
            {
                "plan": plan_b.id,
                "min_sales": "0.00",
                "max_sales": "1000.00",
                "commission_percent": "5.00",
            },
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(CompensationTier.objects.count(), 0)


@override_settings(LOGIN_LOCKOUT_THRESHOLD=3)
class LoginSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(slug="sec-login", name="Sec Login")
        self.user, _, _ = _make_user("locked@test.com", self.org, "Sales Rep", "L1")
        self.client = Client()

    def _login(self, email, password):
        return self.client.post(
            "/api/auth/email-login/",
            {"email": email, "password": password},
            content_type="application/json",
        )

    def test_lockout_after_repeated_failures(self):
        for _ in range(3):
            res = self._login("locked@test.com", "wrong-password")
            self.assertEqual(res.status_code, 401)
        res = self._login("locked@test.com", "test")
        self.assertEqual(res.status_code, 429)

    def test_successful_login_clears_failures(self):
        self._login("locked@test.com", "wrong-password")
        res = self._login("locked@test.com", "test")
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())

    def test_unknown_email_and_wrong_password_are_indistinguishable(self):
        unknown = self._login("ghost@test.com", "whatever-123")
        wrong = self._login("locked@test.com", "wrong-password")
        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.json(), wrong.json())


class LogoutRevocationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(slug="sec-logout", name="Sec Logout")
        self.user, self.auth_client, self.token = _make_user(
            "bye@test.com", self.org, "Sales Rep", "BYE1"
        )

    def test_logout_revokes_token_server_side(self):
        res = self.auth_client.post("/api/auth/logout/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        replay = self.auth_client.get("/api/auth/session/")
        self.assertEqual(replay.status_code, 401)


class PasswordPolicyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(slug="sec-pass", name="Sec Pass")
        self.user, self.auth_client, _ = _make_user(
            "pass@test.com", self.org, "Sales Rep", "P1"
        )

    def test_change_password_rejects_common_password(self):
        res = self.auth_client.post(
            "/api/auth/change-password/",
            {"old_password": "test", "new_password": "password123"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("test"))


@override_settings(MAX_IMPORT_FILE_BYTES=200, MAX_IMPORT_ROWS=2)
class UploadLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(slug="sec-upload", name="Sec Upload")
        self.user, self.auth_client, _ = _make_user(
            "upload-admin@test.com", self.org, "Admin", "UP1"
        )

    def test_oversized_file_rejected(self):
        upload = SimpleUploadedFile(
            "orders.csv",
            b"a" * 500,
            content_type="text/csv",
        )
        res = self.auth_client.post("/api/orders-upload/", {"file": upload})
        self.assertEqual(res.status_code, 400)
        self.assertIn("too large", res.json()["error"].lower())

    def test_too_many_rows_rejected(self):
        content = b"order_id\n" + b"\n".join(b"o%d" % i for i in range(5))
        upload = SimpleUploadedFile("orders.csv", content, content_type="text/csv")
        res = self.auth_client.post("/api/orders-upload/", {"file": upload})
        self.assertEqual(res.status_code, 400)
        self.assertIn("too many rows", res.json()["error"].lower())


class CsvSanitizationTests(TestCase):
    def test_formula_prefixes_are_neutralized(self):
        self.assertEqual(sanitize_csv_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(sanitize_csv_cell("+SUM(A1)"), "'+SUM(A1)")
        self.assertEqual(sanitize_csv_cell("-2+3"), "'-2+3")
        self.assertEqual(sanitize_csv_cell("@cmd"), "'@cmd")

    def test_normal_values_untouched(self):
        self.assertEqual(sanitize_csv_cell("Laxmi"), "Laxmi")
        self.assertEqual(sanitize_csv_cell(1940), 1940)
        self.assertEqual(sanitize_csv_cell(None), "")


@override_settings(INTEGRATIONS_ALLOW_PRIVATE_URLS=False)
class SsrfGuardTests(TestCase):
    def test_private_and_metadata_hosts_blocked(self):
        self.assertFalse(is_public_host("127.0.0.1"))
        self.assertFalse(is_public_host("localhost"))
        self.assertFalse(is_public_host("169.254.169.254"))
        self.assertFalse(is_public_host("10.0.0.5"))
        self.assertFalse(is_public_host("192.168.1.1"))

    def test_unresolvable_host_blocked(self):
        self.assertFalse(is_public_host("definitely-not-a-real-host.invalid"))

    def test_public_ip_allowed(self):
        self.assertTrue(is_public_host("1.1.1.1"))
