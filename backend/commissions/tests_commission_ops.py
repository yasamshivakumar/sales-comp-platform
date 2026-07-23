"""Commission Operations Center API tests — scoping, adjustments, approvals."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.authtoken.models import Token

from .models import (
    Commission,
    CommissionAdjustment,
    CompensationPlan,
    Order,
    SCRateTable,
    UserProfile,
)
from .services import calculate_commission_for_order
from .tenants import get_default_organization


class CommissionOperationsTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.start = date(2026, 7, 1)
        self.end = date(2026, 7, 31)

        self.admin_user = User.objects.create_user(
            username="co-admin", email="co-admin@test.com", password="pass"
        )
        self.finance_user = User.objects.create_user(
            username="co-finance", email="co-finance@test.com", password="pass"
        )
        self.rep_user = User.objects.create_user(
            username="co-rep", email="co-rep@test.com", password="pass"
        )
        self.other_rep = User.objects.create_user(
            username="co-other", email="co-other@test.com", password="pass"
        )

        UserProfile.objects.create(
            organization=self.org,
            employee_id="EMP-CO-1",
            email="co-rep@test.com",
            name="Rep One",
            role="Sales",
            position_name="Sales Rep",
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="EMP-CO-2",
            email="co-other@test.com",
            name="Rep Two",
            role="Sales",
            position_name="Sales Rep",
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="ADM-CO",
            email="co-admin@test.com",
            name="Admin",
            role="Admin",
            position_name="Admin",
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="FIN-CO",
            email="co-finance@test.com",
            name="Finance",
            role="Finance",
            position_name="Finance",
        )

        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="CO Sales Plan",
            position_name="Sales Rep",
            role="Sales",
            status="Active",
            effective_start_date=self.start,
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            from_amount=0,
            to_amount=None,
            commission_rate=Decimal("10.00"),
            bonus_amount=Decimal("0"),
            sequence=1,
            is_active=True,
        )

        self.order = Order.objects.create(
            organization=self.org,
            order_id="CO-ORD-1",
            employee_id="EMP-CO-1",
            position_name="Sales Rep",
            sales_amount=Decimal("50000.00"),
            order_date=date(2026, 7, 15),
            order_status="Success",
            currency="INR",
        )
        calculate_commission_for_order(self.order)
        self.comm = Commission.objects.filter(
            sale__order=self.order
        ).first() or Commission.objects.filter(
            employee__email="co-rep@test.com"
        ).first()
        self.assertIsNotNone(self.comm)

        other_order = Order.objects.create(
            organization=self.org,
            order_id="CO-ORD-2",
            employee_id="EMP-CO-2",
            position_name="Sales Rep",
            sales_amount=Decimal("20000.00"),
            order_date=date(2026, 7, 16),
            order_status="Success",
            currency="INR",
        )
        calculate_commission_for_order(other_order)
        self.other_comm = Commission.objects.filter(sale__order=other_order).first()

        self.client = Client()
        self.admin_auth = {
            "HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=self.admin_user).key}"
        }
        self.finance_auth = {
            "HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=self.finance_user).key}"
        }
        self.rep_auth = {
            "HTTP_AUTHORIZATION": f"Token {Token.objects.create(user=self.rep_user).key}"
        }

    def test_operations_summary_and_grid(self):
        res = self.client.get(
            "/api/commissions/operations-summary/",
            **self.admin_auth,
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("kpis", body)
        self.assertIn("pipeline", body)
        self.assertGreaterEqual(body["kpis"]["record_count"], 1)

        grid = self.client.get(
            "/api/commissions/operations-grid/",
            **self.admin_auth,
        )
        self.assertEqual(grid.status_code, 200)
        rows = grid.json()["results"]
        self.assertTrue(any(r["employee_email"] == "co-rep@test.com" for r in rows))

    def test_rep_only_sees_own_operations(self):
        grid = self.client.get(
            "/api/commissions/operations-grid/",
            **self.rep_auth,
        )
        self.assertEqual(grid.status_code, 200)
        emails = {r["employee_email"].lower() for r in grid.json()["results"]}
        self.assertIn("co-rep@test.com", emails)
        self.assertNotIn("co-other@test.com", emails)

    def test_finance_can_adjust_rep_cannot(self):
        denied = self.client.post(
            "/api/commissions/adjustments/",
            {
                "commission_id": self.comm.id,
                "adjustment_type": "clawback",
                "amount": "500",
                "reason": "Returned order",
            },
            content_type="application/json",
            **self.rep_auth,
        )
        self.assertEqual(denied.status_code, 403)

        ok = self.client.post(
            "/api/commissions/adjustments/",
            {
                "commission_id": self.comm.id,
                "adjustment_type": "clawback",
                "amount": "500",
                "reason": "Returned order",
            },
            content_type="application/json",
            **self.finance_auth,
        )
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(CommissionAdjustment.objects.filter(commission=self.comm).count(), 1)
        adj = CommissionAdjustment.objects.get(commission=self.comm)
        self.assertLess(adj.amount, 0)

        detail = self.client.get(
            f"/api/commissions/operations-detail/?commission_id={self.comm.id}",
            **self.finance_auth,
        )
        self.assertEqual(detail.status_code, 200)
        overview = detail.json()["overview"]
        self.assertTrue(overview["has_adjustments"])
        self.assertEqual(
            Decimal(str(overview["final_commission"])),
            Decimal(str(self.comm.commission_amount)) + adj.amount,
        )

    def test_bulk_finance_approve_and_engine_amount_unchanged(self):
        original = self.comm.commission_amount
        # Manager step first via admin manager approve path: set manager_approved
        self.comm.status = Commission.STATUS_MANAGER_APPROVED
        self.comm.save(update_fields=["status"])

        res = self.client.post(
            "/api/commissions/operations-bulk/",
            {
                "action": "approve_finance",
                "commission_ids": [self.comm.id],
            },
            content_type="application/json",
            **self.finance_auth,
        )
        self.assertEqual(res.status_code, 200)
        self.comm.refresh_from_db()
        self.assertEqual(self.comm.status, Commission.STATUS_APPROVED)
        self.assertEqual(self.comm.commission_amount, original)

    def test_bulk_reject_requires_reason(self):
        bad = self.client.post(
            "/api/commissions/operations-bulk/",
            {"action": "reject", "commission_ids": [self.comm.id]},
            content_type="application/json",
            **self.finance_auth,
        )
        self.assertEqual(bad.status_code, 400)

        ok = self.client.post(
            "/api/commissions/operations-bulk/",
            {
                "action": "reject",
                "commission_ids": [self.comm.id],
                "comment": "Incorrect plan applied",
            },
            content_type="application/json",
            **self.finance_auth,
        )
        self.assertEqual(ok.status_code, 200)
        self.comm.refresh_from_db()
        self.assertEqual(self.comm.status, Commission.STATUS_REJECTED)
        self.assertIn("Incorrect", self.comm.rejection_reason)

    def test_existing_list_api_still_works(self):
        res = self.client.get("/api/commissions/", **self.admin_auth)
        self.assertEqual(res.status_code, 200)
