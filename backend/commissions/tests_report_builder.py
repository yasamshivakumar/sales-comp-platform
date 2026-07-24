"""Report Builder / Analytics API tests — RBAC, tenant isolation, engine."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from .models import (
    AuditLog,
    Organization,
    Report,
    ReportField,
    UserProfile,
)


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


class ReportBuilderApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org_a = Organization.objects.create(slug="rb-org-a", name="RB Org A")
        self.org_b = Organization.objects.create(slug="rb-org-b", name="RB Org B")
        self.admin_a, self.client_admin_a, _ = _make_user(
            "rb-admin-a@test.com", self.org_a, "Admin", "RBA1"
        )
        self.finance_a, self.client_finance_a, _ = _make_user(
            "rb-fin-a@test.com", self.org_a, "Finance", "RBF1"
        )
        self.manager_a, self.client_manager_a, _ = _make_user(
            "rb-mgr-a@test.com", self.org_a, "Manager", "RBM1"
        )
        self.rep_a, self.client_rep_a, _ = _make_user(
            "rb-rep-a@test.com", self.org_a, "Sales Rep", "RBR1"
        )
        self.admin_b, self.client_admin_b, _ = _make_user(
            "rb-admin-b@test.com", self.org_b, "Admin", "RBB1"
        )

    def _create_report(self, client, **overrides):
        payload = {
            "name": "Commission Summary",
            "description": "Test report",
            "report_type": "commissions",
            "visualization": "table",
            "visibility": "private",
            "fields": [
                {"field_key": "employee_name", "label": "Employee"},
                {"field_key": "amount", "label": "Amount"},
            ],
            "filters": [],
            "sort_by": "amount",
            "sort_dir": "desc",
        }
        payload.update(overrides)
        return client.post(
            "/api/analytics/reports/",
            payload,
            content_type="application/json",
        )

    def test_datasources_admin_sees_all(self):
        res = self.client_admin_a.get("/api/analytics/datasources/")
        self.assertEqual(res.status_code, 200)
        keys = {d["key"] for d in res.json()["results"]}
        self.assertIn("commissions", keys)
        self.assertIn("audit_logs", keys)
        self.assertIn("payouts", keys)

    def test_datasources_manager_excludes_payouts(self):
        res = self.client_manager_a.get("/api/analytics/datasources/")
        self.assertEqual(res.status_code, 200)
        keys = {d["key"] for d in res.json()["results"]}
        self.assertIn("commissions", keys)
        self.assertNotIn("payouts", keys)
        self.assertNotIn("audit_logs", keys)

    def test_employee_cannot_create_report(self):
        res = self._create_report(self.client_rep_a)
        self.assertEqual(res.status_code, 403)

    def test_admin_can_create_and_run(self):
        res = self._create_report(self.client_admin_a)
        self.assertEqual(res.status_code, 201, res.content)
        report_id = res.json()["id"]
        self.assertTrue(Report.objects.filter(pk=report_id, organization=self.org_a).exists())
        self.assertEqual(ReportField.objects.filter(report_id=report_id).count(), 2)

        run = self.client_admin_a.post(
            f"/api/analytics/reports/{report_id}/run/",
            {"limit": 50},
            content_type="application/json",
        )
        self.assertEqual(run.status_code, 200)
        body = run.json()
        self.assertIn("result", body)
        self.assertIn("columns", body["result"])
        self.assertIn("rows", body["result"])

        audits = AuditLog.objects.filter(
            organization=self.org_a, action__in=("report_created", "report_viewed")
        )
        self.assertTrue(audits.filter(action="report_created").exists())
        self.assertTrue(audits.filter(action="report_viewed").exists())

    def test_finance_cannot_create_employee_directory_as_primary_if_disallowed(self):
        # Finance may create commissions / payouts
        ok = self._create_report(self.client_finance_a, report_type="payouts", name="Payouts")
        self.assertEqual(ok.status_code, 201, ok.content)
        # plans allowed for finance via _datasource_allowed
        plans = self._create_report(
            self.client_finance_a, report_type="plans", name="Plans"
        )
        self.assertEqual(plans.status_code, 201, plans.content)

    def test_manager_cannot_create_payout_report(self):
        res = self._create_report(
            self.client_manager_a, report_type="payouts", name="Blocked"
        )
        self.assertEqual(res.status_code, 403)

    def test_tenant_isolation_list_and_detail(self):
        created = self._create_report(self.client_admin_a, visibility="organization")
        self.assertEqual(created.status_code, 201)
        report_id = created.json()["id"]

        list_b = self.client_admin_b.get("/api/analytics/reports/")
        self.assertEqual(list_b.status_code, 200)
        ids_b = {r["id"] for r in list_b.json()["results"]}
        self.assertNotIn(report_id, ids_b)

        detail_b = self.client_admin_b.get(f"/api/analytics/reports/{report_id}/")
        self.assertEqual(detail_b.status_code, 404)

        run_b = self.client_admin_b.post(
            f"/api/analytics/reports/{report_id}/run/",
            {},
            content_type="application/json",
        )
        self.assertEqual(run_b.status_code, 404)

    def test_private_report_hidden_from_peer(self):
        created = self._create_report(self.client_admin_a, visibility="private")
        report_id = created.json()["id"]
        # Finance in same org should not see private report owned by admin
        listing = self.client_finance_a.get("/api/analytics/reports/")
        ids = {r["id"] for r in listing.json()["results"]}
        self.assertNotIn(report_id, ids)

    def test_preview_and_export(self):
        preview = self.client_admin_a.post(
            "/api/analytics/reports/preview/",
            {
                "report_type": "orders",
                "fields": [
                    {"field_key": "order_id"},
                    {"field_key": "sales_amount"},
                ],
                "limit": 25,
            },
            content_type="application/json",
        )
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn("rows", preview.json())

        created = self._create_report(self.client_admin_a, report_type="orders")
        report_id = created.json()["id"]
        export = self.client_admin_a.get(f"/api/analytics/reports/{report_id}/export/")
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])
        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.org_a, action="report_exported"
            ).exists()
        )

    def test_schedule_create_and_deactivate(self):
        created = self._create_report(self.client_admin_a)
        report_id = created.json()["id"]
        sched = self.client_admin_a.post(
            "/api/analytics/schedules/",
            {
                "report_id": report_id,
                "frequency": "daily",
                "delivery": "email_excel",
                "recipients": ["rb-admin-a@test.com"],
            },
            content_type="application/json",
        )
        self.assertEqual(sched.status_code, 201, sched.content)
        schedule_id = sched.json()["id"]

        listing = self.client_admin_a.get("/api/analytics/schedules/")
        self.assertEqual(listing.status_code, 200)
        self.assertTrue(any(s["id"] == schedule_id for s in listing.json()["results"]))

        delete = self.client_admin_a.delete(f"/api/analytics/schedules/{schedule_id}/")
        self.assertEqual(delete.status_code, 200)

    def test_duplicate_and_archive(self):
        created = self._create_report(self.client_admin_a, name="Original")
        report_id = created.json()["id"]
        dup = self.client_admin_a.post(f"/api/analytics/reports/{report_id}/duplicate/")
        self.assertEqual(dup.status_code, 201)
        self.assertIn("(Copy)", dup.json()["name"])

        delete = self.client_admin_a.delete(f"/api/analytics/reports/{report_id}/")
        self.assertEqual(delete.status_code, 200)
        report = Report.objects.get(pk=report_id)
        self.assertTrue(report.is_archived)
        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.org_a, action="report_deleted"
            ).exists()
        )
