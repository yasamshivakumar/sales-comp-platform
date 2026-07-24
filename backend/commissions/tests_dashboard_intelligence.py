"""Sales Compensation Intelligence Dashboard tests."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from .models import (
    Commission,
    CompensationPlan,
    Employee,
    HierarchyRelationship,
    Order,
    Organization,
    Sale,
    UserProfile,
)


def _auth(email, org, role, employee_id=None):
    user = User.objects.create_user(username=email, email=email, password="test")
    eid = employee_id or email.split("@")[0][:10]
    UserProfile.objects.create(
        organization=org,
        email=email,
        username=email,
        employee_id=eid,
        name=eid,
        role=role,
        enable_login=True,
        personal_target=Decimal("100000"),
    )
    token = Token.objects.create(user=user)
    return user, Client(HTTP_AUTHORIZATION=f"Token {token.key}"), eid


class IntelligenceDashboardTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(slug="intel-a", name="Intel A")
        self.admin, self.client_admin, _ = _auth(
            "intel-admin@test.com", self.org, "Admin", "IA1"
        )
        self.mgr, self.client_mgr, self.mgr_eid = _auth(
            "intel-mgr@test.com", self.org, "Manager", "IM1"
        )
        self.rep, self.client_rep, self.rep_eid = _auth(
            "intel-rep@test.com", self.org, "Sales Rep", "IR1"
        )
        mgr_p = UserProfile.objects.get(email="intel-mgr@test.com")
        rep_p = UserProfile.objects.get(email="intel-rep@test.com")
        HierarchyRelationship.objects.create(
            parent_participant=mgr_p,
            child_participant=rep_p,
            is_active=True,
            split_percentage=100,
        )
        self.emp = Employee.objects.create(
            organization=self.org, name="Rep", email="intel-rep@test.com"
        )
        CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Exec Plan",
            status="Active",
            role="Sales Rep",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 12, 31),
        )
        today = date.today()
        order = Order.objects.create(
            organization=self.org,
            order_id="INT-1",
            employee_id=self.rep_eid,
            order_date=today,
            sales_amount=Decimal("50000"),
            order_status="Success",
            currency="INR",
        )
        sale = Sale.objects.create(
            organization=self.org,
            employee=self.emp,
            order=order,
            employee_salary=Decimal("0"),
            amount=Decimal("50000"),
        )
        Commission.objects.create(
            organization=self.org,
            employee=self.emp,
            sale=sale,
            commission_amount=Decimal("2500"),
            status=Commission.STATUS_CALCULATED,
        )

    def test_admin_gets_intelligence_payload(self):
        end = date.today()
        start = end - timedelta(days=30)
        res = self.client_admin.get(
            f"/api/reports/command-center/?start_date={start}&end_date={end}"
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["view_mode"], "organization")
        self.assertIn("kpi_cards", body)
        self.assertIn("processing_status", body)
        self.assertIn("forecast", body)
        self.assertIn("attainment_distribution", body)
        self.assertIn("plan_performance", body)
        self.assertIn("top_performers", body)
        self.assertIn("leakage", body)
        self.assertGreaterEqual(body["kpis"]["total_sales"], 0)

    def test_manager_is_team_scoped(self):
        end = date.today()
        start = end - timedelta(days=30)
        res = self.client_mgr.get(
            f"/api/reports/command-center/?start_date={start}&end_date={end}"
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["view_mode"], "team")
        self.assertIsNotNone(body.get("team_summary"))

    def test_rep_forbidden(self):
        res = self.client_rep.get("/api/reports/command-center/")
        self.assertEqual(res.status_code, 403)

    def test_export_csv(self):
        res = self.client_admin.get("/api/reports/command-center/export/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res["Content-Type"])
        self.assertIn(b"Intelligence", res.content)
