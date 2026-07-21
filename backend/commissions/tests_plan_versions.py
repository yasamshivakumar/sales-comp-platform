"""Tests for enterprise Commission Plan Versioning."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from commissions.models import (
    Commission,
    CommissionPlanVersion,
    CompensationPlan,
    Organization,
    Order,
    PlanVersionQuota,
    SCRateTable,
    UserProfile,
)
from commissions.plan_versions import (
    PlanVersionError,
    archive_version,
    clone_version,
    publish_version,
)
from commissions.services import calculate_commission_for_order
from commissions.tenants import get_default_organization


class PlanVersionModelTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Sales Executive Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 3, 31),
        )
        self.v1 = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=1,
            status=CommissionPlanVersion.STATUS_DRAFT,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 3, 31),
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=self.v1,
            from_amount=0,
            to_amount=None,
            commission_rate=Decimal("5.00"),
            sequence=1,
        )

    def test_publish_makes_immutable(self):
        publish_version(self.v1, strict=True)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.status, CommissionPlanVersion.STATUS_PUBLISHED)
        self.assertIsNotNone(self.v1.published_at)

    def test_publish_rejects_missing_rates(self):
        publish_version(self.v1, strict=True)
        empty = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=2,
            status=CommissionPlanVersion.STATUS_DRAFT,
            effective_from=date(2026, 4, 1),
            effective_to=date(2026, 12, 31),
            role="Sales Rep",
            commission_table_type="RATE",
        )
        with self.assertRaises(PlanVersionError):
            publish_version(empty, strict=True)

    def test_clone_deep_copies_rates_and_quotas(self):
        publish_version(self.v1, strict=True)
        PlanVersionQuota.objects.create(
            plan_version=self.v1, year=2026, month=1, quota_amount=Decimal("1000000")
        )
        draft = clone_version(self.v1)
        self.assertEqual(draft.status, CommissionPlanVersion.STATUS_DRAFT)
        self.assertEqual(draft.version_number, 2)
        self.assertEqual(draft.sc_rate_tables.count(), 1)
        self.assertEqual(draft.quotas.count(), 1)
        self.assertNotEqual(draft.sc_rate_tables.first().pk, self.v1.sc_rate_tables.first().pk)

    def test_publish_supersedes_earlier_version_by_end_dating(self):
        """Publishing over an older version that started earlier trims the
        old version's end date instead of raising an overlap error."""
        publish_version(self.v1, strict=True)
        draft = clone_version(self.v1)
        draft.effective_from = date(2026, 2, 1)
        draft.effective_to = date(2026, 6, 30)
        draft.save()
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=draft,
            from_amount=0,
            commission_rate=Decimal("7.00"),
            sequence=1,
        )
        published = publish_version(draft, strict=True)
        self.assertEqual(published.status, CommissionPlanVersion.STATUS_PUBLISHED)
        self.v1.refresh_from_db()
        # v1 keeps its history but now ends the day before v2 starts.
        self.assertEqual(self.v1.status, CommissionPlanVersion.STATUS_PUBLISHED)
        self.assertEqual(self.v1.effective_to, date(2026, 1, 31))
        self.assertEqual(
            published.superseded_versions,
            [
                {
                    "version_number": 1,
                    "action": "end_dated",
                    "effective_to": "2026-01-31",
                }
            ],
        )

    def test_publish_supersedes_same_range_by_archiving(self):
        """Publishing a draft with the same (or covering) date range archives
        the replaced version automatically."""
        publish_version(self.v1, strict=True)
        draft = clone_version(self.v1)
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=draft,
            from_amount=0,
            commission_rate=Decimal("7.00"),
            sequence=2,
        )
        published = publish_version(draft, strict=True)
        self.assertEqual(published.status, CommissionPlanVersion.STATUS_PUBLISHED)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.status, CommissionPlanVersion.STATUS_ARCHIVED)
        self.assertEqual(
            published.superseded_versions,
            [{"version_number": 1, "action": "archived"}],
        )

    def test_archive_published(self):
        publish_version(self.v1, strict=True)
        archive_version(self.v1)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.status, CommissionPlanVersion.STATUS_ARCHIVED)


class PlanVersionCalculationTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.user = User.objects.create_user(
            username="rep@calc.co", email="rep@calc.co", password="x"
        )
        UserProfile.objects.create(
            organization=self.org,
            email="rep@calc.co",
            name="Rep",
            employee_id="E100",
            role="Sales Rep",
            enable_login=True,
        )
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="SE Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 12, 31),
        )
        self.v1 = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=1,
            status=CommissionPlanVersion.STATUS_PUBLISHED,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 3, 31),
            role="Sales Rep",
            commission_table_type="RATE",
            published_at=date(2026, 1, 1),
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=self.v1,
            from_amount=0,
            commission_rate=Decimal("5.00"),
            sequence=1,
        )
        self.v2 = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=2,
            status=CommissionPlanVersion.STATUS_PUBLISHED,
            effective_from=date(2026, 4, 1),
            effective_to=date(2026, 12, 31),
            role="Sales Rep",
            commission_table_type="RATE",
            published_at=date(2026, 4, 1),
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=self.v2,
            from_amount=0,
            commission_rate=Decimal("10.00"),
            sequence=1,
        )

    def _order(self, order_date, amount="100000"):
        return Order.objects.create(
            organization=self.org,
            order_id=f"ORD-{order_date}",
            employee_id="E100",
            order_date=order_date,
            sales_amount=Decimal(amount),
            order_status="Success",
            currency="INR",
        )

    def test_february_uses_version_1(self):
        order = self._order(date(2026, 2, 15))
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.plan_version_id, self.v1.id)
        self.assertEqual(commission.commission_amount, Decimal("5000.00"))

    def test_may_uses_version_2(self):
        order = self._order(date(2026, 5, 10))
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.plan_version_id, self.v2.id)
        self.assertEqual(commission.commission_amount, Decimal("10000.00"))

    def test_draft_never_used_for_calc(self):
        draft = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=3,
            status=CommissionPlanVersion.STATUS_DRAFT,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=draft,
            from_amount=0,
            commission_rate=Decimal("99.00"),
            sequence=1,
        )
        order = self._order(date(2026, 2, 20), amount="200000")
        commission = calculate_commission_for_order(order)
        self.assertEqual(commission.plan_version_id, self.v1.id)
        self.assertNotEqual(commission.commission_amount, Decimal("198000.00"))

    def test_historical_commission_keeps_original_version(self):
        order = self._order(date(2026, 2, 15))
        commission = calculate_commission_for_order(order)
        original_version_id = commission.plan_version_id
        original_amount = commission.commission_amount
        # Mutating a draft must not rewrite history.
        draft = clone_version(self.v1)
        rate = draft.sc_rate_tables.first()
        rate.commission_rate = Decimal("50.00")
        rate.save()
        commission.refresh_from_db()
        self.assertEqual(commission.plan_version_id, original_version_id)
        self.assertEqual(commission.commission_amount, original_amount)


class PlanVersionAPITests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.admin = User.objects.create_user(
            username="admin@api.co", email="admin@api.co", password="x"
        )
        UserProfile.objects.create(
            organization=self.org,
            email="admin@api.co",
            name="Admin",
            role="Admin",
            enable_login=True,
        )
        self.token = Token.objects.create(user=self.admin)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="API Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 3, 31),
        )
        self.v1 = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=1,
            status=CommissionPlanVersion.STATUS_PUBLISHED,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 3, 31),
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=self.v1,
            from_amount=0,
            commission_rate=Decimal("5.00"),
            sequence=1,
        )

    def test_list_versions(self):
        res = self.client.get(f"/api/compensation-plans/{self.plan.id}/versions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

    def test_clone_publish_flow(self):
        res = self.client.post(
            f"/api/compensation-plans/{self.plan.id}/versions/{self.v1.id}/clone/"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        draft_id = res.data["id"]
        self.assertEqual(res.data["status"], "Draft")

        # Set non-overlapping dates then publish.
        self.client.patch(
            f"/api/compensation-plans/{self.plan.id}/versions/{draft_id}/",
            {
                "effective_from": "2026-04-01",
                "effective_to": "2026-12-31",
                "sc_rate_tables": [
                    {
                        "from_amount": "0",
                        "commission_rate": "8.00",
                        "bonus_amount": "0",
                        "sequence": 1,
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )
        res = self.client.post(
            f"/api/compensation-plans/{self.plan.id}/versions/{draft_id}/publish/"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "Published")

    def test_cannot_edit_published_via_plan_patch(self):
        res = self.client.patch(
            f"/api/compensation-plans/{self.plan.id}/",
            {
                "commission_table_type": "FLAT",
                "sc_flat_rate_tables": [
                    {
                        "flat_rate": "3.00",
                        "bonus_amount": "0",
                        "minimum_sales_threshold": "0",
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_legacy_create_still_works(self):
        res = self.client.post(
            "/api/compensation-plans/",
            {
                "plan_name": "Legacy Create Plan",
                "status": "Active",
                "role": "Sales Rep",
                "commission_table_type": "RATE",
                "effective_start_date": "2026-06-01",
                "effective_end_date": "2026-06-30",
                "sc_rate_tables": [
                    {
                        "from_amount": "0",
                        "commission_rate": "4.00",
                        "bonus_amount": "0",
                        "sequence": 1,
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        plan = CompensationPlan.objects.get(id=res.data["id"])
        self.assertEqual(plan.versions.count(), 1)
        self.assertEqual(
            plan.versions.first().status, CommissionPlanVersion.STATUS_PUBLISHED
        )
        self.assertIn("current_version", res.data)

    def test_create_without_rates_then_add_rates_publishes_v1(self):
        """Legacy UI flow: plan header is created Active first, rate rows are
        added afterwards. v1 must not be published while empty (an empty
        Published version blocks calculation) and must auto-publish once the
        first rates arrive, so commissions generate without the version UI."""
        res = self.client.post(
            "/api/compensation-plans/",
            {
                "plan_name": "Two-Step Plan",
                "status": "Active",
                "role": "Sales Rep",
                "commission_table_type": "RATE",
                "effective_start_date": "2026-07-01",
                "effective_end_date": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        plan = CompensationPlan.objects.get(id=res.data["id"])
        v1 = plan.versions.get()
        self.assertEqual(v1.status, CommissionPlanVersion.STATUS_DRAFT)

        res = self.client.patch(
            f"/api/compensation-plans/{plan.id}/",
            {
                "sc_rate_tables": [
                    {
                        "from_amount": "10000",
                        "to_amount": "50000",
                        "commission_rate": "0.50",
                        "bonus_amount": "0",
                        "sequence": 1,
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        v1.refresh_from_db()
        self.assertEqual(v1.status, CommissionPlanVersion.STATUS_PUBLISHED)

        UserProfile.objects.create(
            organization=self.org,
            employee_id="EMPV1",
            email="empv1@api.co",
            name="Emp V1",
            role="Sales Rep",
        )
        order = Order.objects.create(
            organization=self.org,
            order_id="ORD-V1-1",
            employee_id="EMPV1",
            sales_amount=Decimal("14989.00"),
            order_date=date(2026, 7, 14),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.plan_version_id, v1.id)

    def test_compare_versions(self):
        draft = clone_version(self.v1)
        res = self.client.get(
            f"/api/compensation-plans/{self.plan.id}/versions/compare/",
            {"left": self.v1.id, "right": draft.id},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("header_diff", res.data)
        self.assertIn("rate_tables", res.data)

    def test_org_isolation(self):
        other = Organization.objects.create(name="Other", slug="other-pv")
        other_plan = CompensationPlan.objects.create(
            organization=other,
            plan_name="Other Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 1, 31),
        )
        res = self.client.get(f"/api/compensation-plans/{other_plan.id}/versions/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class PlanVersionMigrationRegressionTests(TestCase):
    """Existing Active monthly plans must still calculate the same amounts
    after backfill into Version 1."""

    def setUp(self):
        self.org = get_default_organization()
        UserProfile.objects.create(
            organization=self.org,
            email="rep@reg.co",
            name="Rep",
            employee_id="R1",
            role="Sales Rep",
        )
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Jan Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
            effective_end_date=date(2026, 1, 31),
        )
        version = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            version_number=1,
            status=CommissionPlanVersion.STATUS_PUBLISHED,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 1, 31),
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            plan_version=version,
            from_amount=0,
            commission_rate=Decimal("6.00"),
            sequence=1,
        )

    def test_january_order_still_calculates(self):
        order = Order.objects.create(
            organization=self.org,
            order_id="REG-1",
            employee_id="R1",
            order_date=date(2026, 1, 12),
            sales_amount=Decimal("50000"),
            order_status="Success",
            currency="INR",
        )
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("3000.00"))
        self.assertEqual(commission.plan_version.version_number, 1)


class PerOrderRateTierTests(TestCase):
    """RATE tables: each order picks its own tier band, and the monthly
    commission is the sum of per-order commissions (orders are never
    summed before the tier lookup)."""

    def setUp(self):
        self.org = get_default_organization()
        UserProfile.objects.create(
            organization=self.org,
            email="tier@calc.co",
            name="Tier Rep",
            employee_id="TIER1",
            role="Sales Rep",
        )

    def _build_plan(self):
        plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Per-order Tier Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 3, 1),
            effective_end_date=date(2026, 3, 31),
        )
        version = CommissionPlanVersion.objects.create(
            organization=self.org,
            compensation_plan=plan,
            version_number=1,
            status=CommissionPlanVersion.STATUS_PUBLISHED,
            effective_from=date(2026, 3, 1),
            effective_to=date(2026, 3, 31),
            role="Sales Rep",
            commission_table_type="RATE",
        )
        tiers = [
            (Decimal("0"), Decimal("10000"), Decimal("0.5")),
            (Decimal("10000"), Decimal("50000"), Decimal("1.0")),
            (Decimal("50000"), None, Decimal("1.5")),
        ]
        for idx, (lo, hi, rate) in enumerate(tiers, start=1):
            SCRateTable.objects.create(
                compensation_plan=plan,
                plan_version=version,
                from_amount=lo,
                to_amount=hi,
                commission_rate=rate,
                sequence=idx,
                is_active=True,
            )
        return plan

    def _order(self, order_id, amount):
        return Order.objects.create(
            organization=self.org,
            order_id=order_id,
            employee_id="TIER1",
            order_date=date(2026, 3, 10),
            sales_amount=Decimal(amount),
            order_status="Success",
            currency="INR",
        )

    def test_single_order_uses_landing_tier_rate_on_whole_amount(self):
        self._build_plan()
        commission = calculate_commission_for_order(self._order("ORD-30k", "30000"))
        self.assertIsNotNone(commission)
        # 30,000 lands in the 10k-50k tier -> 1% of the whole 30,000.
        self.assertEqual(commission.commission_amount, Decimal("300.00"))

    def test_orders_are_tiered_individually_then_summed(self):
        self._build_plan()
        self._order("ORD-A", "15000")   # 10k-50k tier -> 1% = 150
        self._order("ORD-B", "8000")    # 0-10k tier -> 0.5% = 40
        last = self._order("ORD-C", "55000")  # 50k+ tier -> 1.5% = 825
        commission = calculate_commission_for_order(last)
        self.assertIsNotNone(commission)
        # Orders are NOT summed first (78,000 would land in 50k+ at 1.5%
        # = 1,170); each order is tiered on its own: 150 + 40 + 825.
        self.assertEqual(commission.commission_amount, Decimal("1015.00"))

    def test_order_above_all_capped_tiers_earns_nothing_for_that_order(self):
        plan = self._build_plan()
        # Cap the top tier at 100k so a bigger order matches no band.
        SCRateTable.objects.filter(
            compensation_plan=plan, to_amount__isnull=True
        ).update(to_amount=Decimal("100000"))
        self._order("ORD-IN", "20000")    # 1% = 200
        last = self._order("ORD-OUT", "150000")  # no band -> 0
        commission = calculate_commission_for_order(last)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("200.00"))
