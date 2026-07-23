"""Activity & Compliance Center (AuditLog) tests."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from .audit import diff_fields, record_audit
from .models import AuditLog, Organization, UserProfile


def _auth_client(email, org, role):
    user = User.objects.create_user(username=email, email=email, password="test")
    UserProfile.objects.create(
        organization=org,
        email=email,
        username=email,
        employee_id=email.split("@")[0][:8],
        name=email.split("@")[0],
        role=role,
        enable_login=True,
    )
    token = Token.objects.create(user=user)
    return user, Client(HTTP_AUTHORIZATION=f"Token {token.key}")


class AuditImmutabilityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(slug="audit-imm", name="Audit Imm")
        self.user, self.client = _auth_client("admin@audit.test", self.org, "Admin")
        record_audit(
            None,
            "settings_changed",
            {"note": "seed"},
            user=self.user,
            organization=self.org,
        )
        self.row = AuditLog.objects.filter(organization=self.org).first()

    def test_instance_update_blocked(self):
        self.row.action = "tampered"
        with self.assertRaises(ValueError):
            self.row.save()

    def test_instance_delete_blocked(self):
        with self.assertRaises(ValueError):
            self.row.delete()

    def test_queryset_update_blocked(self):
        with self.assertRaises(ValueError):
            AuditLog.objects.filter(pk=self.row.pk).update(action="tampered")


class AuditActivityApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org_a = Organization.objects.create(slug="act-a", name="Act A")
        self.org_b = Organization.objects.create(slug="act-b", name="Act B")
        self.admin, self.client_admin = _auth_client("act-admin@test.com", self.org_a, "Admin")
        self.rep, self.client_rep = _auth_client("act-rep@test.com", self.org_a, "Sales Rep")
        self.finance, self.client_finance = _auth_client(
            "act-fin@test.com", self.org_a, "Finance"
        )
        record_audit(
            None,
            "login_success",
            {"email": "act-admin@test.com"},
            user=self.admin,
            organization=self.org_a,
        )
        record_audit(
            None,
            "login_failed",
            {"email": "attacker@test.com"},
            organization=self.org_a,
            status="failed",
        )
        record_audit(
            None,
            "role_changed",
            {"profile_id": 1},
            user=self.admin,
            organization=self.org_a,
            old_value={"role": "Sales Rep"},
            new_value={"role": "Manager"},
            changed_fields=["role"],
        )
        record_audit(
            None,
            "order_created",
            {"order_id": "OB1"},
            organization=self.org_b,
        )

    def test_list_requires_admin_or_finance(self):
        res = self.client_rep.get("/api/audit-logs/")
        self.assertEqual(res.status_code, 403)
        res = self.client_admin.get("/api/audit-logs/")
        self.assertEqual(res.status_code, 200)

    def test_list_is_org_scoped_and_paginated(self):
        res = self.client_admin.get("/api/audit-logs/?page_size=10")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("page", body)
        actions = {row["action"] for row in body["results"]}
        self.assertNotIn("order_created", actions)
        self.assertIn("login_success", actions)

    def test_filter_by_severity_and_search(self):
        res = self.client_admin.get("/api/audit-logs/?severity=warning")
        self.assertEqual(res.status_code, 200)
        for row in res.json()["results"]:
            self.assertEqual(row["severity"], "warning")

        res = self.client_admin.get("/api/audit-logs/?q=role")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(r["action"] == "role_changed" for r in res.json()["results"]))

    def test_detail_includes_old_new(self):
        row = AuditLog.objects.filter(organization=self.org_a, action="role_changed").first()
        res = self.client_admin.get(f"/api/audit-logs/{row.id}/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["old_value"]["role"], "Sales Rep")
        self.assertEqual(body["new_value"]["role"], "Manager")
        self.assertIn("role", body["changed_fields"])

    def test_summary_and_security(self):
        res = self.client_admin.get("/api/audit-logs/summary/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("today_activities", res.json())

        res = self.client_finance.get("/api/audit-logs/security/")
        self.assertEqual(res.status_code, 200)
        actions = {r["action"] for r in res.json()["results"]}
        self.assertTrue(actions & {"login_failed", "role_changed"})

    def test_export_admin_ok_and_self_audits(self):
        before = AuditLog.objects.filter(organization=self.org_a, action="audit_export").count()
        res = self.client_admin.get("/api/audit-logs/export/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res["Content-Type"])
        after = AuditLog.objects.filter(organization=self.org_a, action="audit_export").count()
        self.assertEqual(after, before + 1)

    def test_export_rep_forbidden(self):
        res = self.client_rep.get("/api/audit-logs/export/")
        self.assertEqual(res.status_code, 403)

    def test_diff_fields_helper(self):
        self.assertEqual(
            diff_fields({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4}),
            ["b", "c"],
        )
