from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .tenants import get_default_organization
from .models import (
    UserProfile,
    CompensationPlan,
    SCRateTable,
    HierarchyRelationship,
    Order,
    Commission,
    Employee,
)
from .services import (
    resolve_compensation_plan,
    calculate_commission_for_order,
    clear_commissions_for_order,
    approve_commissions,
)


class CommissionLogicTests(TestCase):
    """Verify role, position, and hierarchy commission behavior."""

    def setUp(self):
        self.start = date(2025, 1, 1)
        self.org = get_default_organization()

        self.rep = UserProfile.objects.create(
            organization=self.org,
            employee_id="REP001",
            email="rep@test.com",
            name="Sales Rep One",
            role="Sales Rep",
            position_name="Standard Rep Position",
        )
        self.senior = UserProfile.objects.create(
            organization=self.org,
            employee_id="SR001",
            email="senior@test.com",
            name="Senior Rep",
            role="Sales Rep",
            position_name="Enterprise AE",
        )
        self.manager = UserProfile.objects.create(
            organization=self.org,
            employee_id="MGR001",
            email="mgr@test.com",
            name="Manager",
            role="Manager",
            position_name="Sales Manager",
        )

        # Role-only plan: 5% for all Sales Reps (no position on plan)
        self.role_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Sales Rep Role Plan",
            effective_start_date=self.start,
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.role_plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("5"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )

        # Position-specific plan: 10% for Enterprise AE only
        self.position_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Enterprise AE Plan",
            effective_start_date=self.start,
            status="Active",
            role="Sales Rep",
            position_name="Enterprise AE",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.position_plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("10"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )

        # Manager role plan: 8%
        self.manager_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Manager Role Plan",
            effective_start_date=self.start,
            status="Active",
            role="Manager",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.manager_plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("8"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )

        HierarchyRelationship.objects.create(
            parent_participant=self.manager,
            child_participant=self.rep,
            split_percentage=Decimal("80"),
            is_active=True,
        )

    def _order(self, order_id, employee_id, sales_amount, position_name=None):
        return Order.objects.create(
            organization=self.org,
            order_id=order_id,
            order_date=self.start,
            employee_id=employee_id,
            position_name=position_name,
            sales_amount=Decimal(sales_amount),
        )

    def test_resolve_role_plan_when_no_position_match(self):
        order = self._order(
            "O-ROLE",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        plan, source = resolve_compensation_plan(order)
        self.assertEqual(plan, self.role_plan)
        self.assertEqual(source, "role:Sales Rep")

    def test_resolve_position_plan_over_role(self):
        order = self._order(
            "O-POS",
            "SR001",
            "10000",
            position_name="Enterprise AE",
        )
        plan, source = resolve_compensation_plan(order)
        self.assertEqual(plan, self.position_plan)
        self.assertEqual(source, "position_name:Enterprise AE")

    def test_position_on_profile_when_order_has_no_position(self):
        order = self._order("O-PROF-POS", "SR001", "10000", position_name=None)
        plan, source = resolve_compensation_plan(order)
        self.assertEqual(plan, self.position_plan)
        self.assertEqual(source, "position_name:Enterprise AE")

    def test_role_plan_not_used_when_position_plan_exists_for_other_position(self):
        """Rep with standard position should not pick Enterprise AE plan."""
        order = self._order(
            "O-STD",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        plan, _ = resolve_compensation_plan(order)
        self.assertEqual(plan, self.role_plan)

    def test_commission_amount_uses_position_rate(self):
        order = self._order(
            "O-CALC-POS",
            "SR001",
            "10000",
            position_name="Enterprise AE",
        )
        calculate_commission_for_order(order)
        comm = Commission.objects.get(employee__email="senior@test.com")
        self.assertEqual(comm.commission_amount, Decimal("1000.00"))

    def test_commission_amount_uses_role_rate(self):
        order = self._order(
            "O-CALC-ROLE",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        calculate_commission_for_order(order)
        comm = Commission.objects.get(employee__email="rep@test.com")
        self.assertEqual(comm.commission_amount, Decimal("400.00"))

    def test_hierarchy_split_child_and_parent(self):
        order = self._order(
            "O-HIER",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        calculate_commission_for_order(order)
        # 5% of 10000 = 500; child keeps 80% = 400, parent 20% = 100
        rep_comm = Commission.objects.get(employee__email="rep@test.com")
        mgr_comm = Commission.objects.get(employee__email="mgr@test.com")
        self.assertEqual(rep_comm.commission_amount, Decimal("400.00"))
        self.assertEqual(mgr_comm.commission_amount, Decimal("100.00"))

    def test_hierarchy_default_100_child_keeps_all(self):
        HierarchyRelationship.objects.filter(
            child_participant=self.rep
        ).update(split_percentage=Decimal("100"))
        order = self._order(
            "O-HIER-100",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        Commission.objects.all().delete()
        calculate_commission_for_order(order)
        rep_comm = Commission.objects.get(employee__email="rep@test.com")
        self.assertEqual(rep_comm.commission_amount, Decimal("500.00"))
        self.assertFalse(
            Commission.objects.filter(employee__email="mgr@test.com").exists()
        )

    def test_manager_order_uses_manager_plan(self):
        order = self._order(
            "O-MGR",
            "MGR001",
            "10000",
            position_name="Sales Manager",
        )
        plan, source = resolve_compensation_plan(order)
        self.assertEqual(plan, self.manager_plan)
        self.assertEqual(source, "role:Manager")

    def test_no_plan_returns_none(self):
        order = self._order("O-NONE", "UNKNOWN", "10000")
        plan, source = resolve_compensation_plan(order)
        self.assertIsNone(plan)
        self.assertIsNone(source)
        self.assertIsNone(calculate_commission_for_order(order))

    def test_reupload_order_does_not_duplicate_commission(self):
        UserProfile.objects.create(
            organization=self.org,
            employee_id="EMP001",
            email="emp001@test.com",
            name="Solo Rep",
            role="Sales Rep",
            position_name="Standard Sales Rep",
        )
        order = self._order(
            "O-DUP",
            "EMP001",
            "10000",
            position_name="Standard Sales Rep",
        )
        calculate_commission_for_order(order)
        self.assertEqual(Commission.objects.filter(sale__order=order).count(), 1)

        calculate_commission_for_order(order)
        self.assertEqual(Commission.objects.filter(sale__order=order).count(), 1)
        comm = Commission.objects.get(sale__order=order)
        self.assertEqual(comm.commission_amount, Decimal("500.00"))

    def test_plan_effective_dates_filter_by_order_date(self):
        CompensationPlan.objects.filter(
            role="Sales Rep",
            position_name__isnull=True,
        ).update(status="Inactive")
        CompensationPlan.objects.filter(role="Sales Rep", position_name="").update(
            status="Inactive"
        )

        old_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Rep Plan 2025 H1",
            effective_start_date=date(2025, 1, 1),
            effective_end_date=date(2025, 6, 30),
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=old_plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("5"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )
        new_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Rep Plan 2025 H2",
            effective_start_date=date(2025, 7, 1),
            effective_end_date=None,
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=new_plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("10"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )

        order_h1 = self._order(
            "O-H1",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        order_h1.order_date = date(2025, 3, 15)
        order_h1.save()
        plan, _ = resolve_compensation_plan(order_h1)
        self.assertEqual(plan, old_plan)

        order_h2 = self._order(
            "O-H2",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        order_h2.order_date = date(2025, 8, 1)
        order_h2.save()
        plan, _ = resolve_compensation_plan(order_h2)
        self.assertEqual(plan, new_plan)

    def test_approved_commission_blocks_recalc_without_force(self):
        UserProfile.objects.create(
            organization=self.org,
            employee_id="EMP002",
            email="emp002@test.com",
            name="Solo Two",
            role="Sales Rep",
            position_name="Other",
        )
        order = self._order("O-LOCK", "EMP002", "10000", position_name="Other")
        calculate_commission_for_order(order)
        comm = Commission.objects.get(sale__order=order)
        approve_commissions(Commission.objects.filter(pk=comm.pk), approved_by_user=None)

        calculate_commission_for_order(order)
        self.assertEqual(Commission.objects.filter(sale__order=order).count(), 1)
        comm.refresh_from_db()
        self.assertEqual(comm.status, Commission.STATUS_APPROVED)

        calculate_commission_for_order(order, force=True)
        self.assertEqual(Commission.objects.filter(sale__order=order).count(), 1)
        new_comm = Commission.objects.get(sale__order=order)
        self.assertEqual(new_comm.status, Commission.STATUS_CALCULATED)


class PilotOperationsTests(TestCase):
    def test_health_and_readiness(self):
        client = Client()
        live = client.get("/api/health/")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json()["status"], "ok")

        ready = client.get("/api/health/ready/")
        self.assertEqual(ready.status_code, 200)
        self.assertTrue(ready.json()["database"])

    def test_audit_log_requires_finance_or_admin(self):
        org = get_default_organization()
        admin_user = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            organization=org,
            employee_id="ADM001",
            email="admin@test.com",
            name="Admin",
            role="Admin",
        )
        rep_user = User.objects.create_user(
            username="rep@test.com",
            email="rep@test.com",
            password="testpass123",
        )
        UserProfile.objects.create(
            organization=org,
            employee_id="REP099",
            email="rep@test.com",
            name="Rep",
            role="Sales Rep",
        )

        admin_token = Token.objects.create(user=admin_user).key
        rep_token = Token.objects.create(user=rep_user).key
        client = Client()

        ok = client.get(
            "/api/audit-logs/",
            HTTP_AUTHORIZATION=f"Token {admin_token}",
        )
        self.assertEqual(ok.status_code, 200)

        denied = client.get(
            "/api/audit-logs/",
            HTTP_AUTHORIZATION=f"Token {rep_token}",
        )
        self.assertEqual(denied.status_code, 403)
