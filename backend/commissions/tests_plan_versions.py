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


class HighestRateTableTests(TestCase):
    """HIGHEST tables: sum successful monthly orders first, then apply the
    matching tier rate to the entire monthly total."""

    def setUp(self):
        self.org = get_default_organization()
        UserProfile.objects.create(
            organization=self.org,
            email="highest@calc.co",
            name="Highest Rep",
            employee_id="HI1",
            role="Sales Rep",
        )

    def _build_plan(self, with_bonus=False):
        plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Highest Rate Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="HIGHEST",
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
            commission_table_type="HIGHEST",
        )
        tiers = [
            (Decimal("0"), Decimal("10000"), Decimal("1.0"), Decimal("0")),
            (Decimal("10000"), Decimal("50000"), Decimal("5.0"), Decimal("0")),
            (Decimal("50000"), Decimal("100000"), Decimal("10.0"), Decimal("0")),
            (
                Decimal("100000"),
                Decimal("200000"),
                Decimal("15.0"),
                Decimal("500.00") if with_bonus else Decimal("0"),
            ),
        ]
        for idx, (lo, hi, rate, bonus) in enumerate(tiers, start=1):
            SCRateTable.objects.create(
                compensation_plan=plan,
                plan_version=version,
                from_amount=lo,
                to_amount=hi,
                commission_rate=rate,
                bonus_amount=bonus,
                sequence=idx,
                is_active=True,
            )
        return plan, version

    def _order(self, order_id, amount, order_date=None):
        return Order.objects.create(
            organization=self.org,
            order_id=order_id,
            employee_id="HI1",
            order_date=order_date or date(2026, 3, 10),
            sales_amount=Decimal(amount),
            order_status="Success",
            currency="INR",
        )

    def test_monthly_sum_selects_highest_matching_tier(self):
        self._build_plan()
        # 30k + 20k + 100k + 50k = 200k -> 100k-200k tier @ 15% = 30,000
        self._order("H-30k", "30000")
        self._order("H-20k", "20000")
        self._order("H-100k", "100000")
        last = self._order("H-50k", "50000")
        commission = calculate_commission_for_order(last)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.source_sales_total, Decimal("200000.00"))
        self.assertEqual(commission.source_order_count, 4)
        self.assertEqual(commission.commission_amount, Decimal("30000.00"))

    def test_recalc_moves_to_higher_tier_when_new_order_arrives(self):
        self._build_plan()
        first = self._order("H-R1", "40000")
        commission = calculate_commission_for_order(first)
        # 40k lands in 10k-50k @ 5% = 2,000
        self.assertEqual(commission.commission_amount, Decimal("2000.00"))

        last = self._order("H-R2", "80000")
        commission = calculate_commission_for_order(last)
        # 40k + 80k = 120k -> 100k-200k @ 15% = 18,000
        self.assertEqual(commission.commission_amount, Decimal("18000.00"))

    def test_bonus_added_on_selected_tier(self):
        self._build_plan(with_bonus=True)
        last = self._order("H-BONUS", "150000")
        commission = calculate_commission_for_order(last)
        # 150k @ 15% + 500 bonus = 22,500 + 500
        self.assertEqual(commission.commission_amount, Decimal("23000.00"))

    def test_open_ended_top_tier(self):
        plan, version = self._build_plan()
        SCRateTable.objects.filter(
            plan_version=version, from_amount=Decimal("100000")
        ).update(to_amount=None)
        last = self._order("H-OPEN", "250000")
        commission = calculate_commission_for_order(last)
        self.assertEqual(commission.commission_amount, Decimal("37500.00"))

    def test_currency_isolation(self):
        self._build_plan()
        self._order("H-INR", "150000")
        usd = Order.objects.create(
            organization=self.org,
            order_id="H-USD",
            employee_id="HI1",
            order_date=date(2026, 3, 12),
            sales_amount=Decimal("150000"),
            order_status="Success",
            currency="USD",
        )
        # USD order alone has no HIGHEST plan currency match via rates on INR
        # buckets — still same plan, but monthly aggregate is currency-scoped.
        commission_usd = calculate_commission_for_order(usd)
        self.assertIsNotNone(commission_usd)
        self.assertEqual(commission_usd.currency.upper(), "USD")
        self.assertEqual(commission_usd.source_sales_total, Decimal("150000.00"))
        self.assertEqual(commission_usd.commission_amount, Decimal("22500.00"))

        inr_order = Order.objects.filter(order_id="H-INR").first()
        commission_inr = calculate_commission_for_order(inr_order)
        self.assertEqual(commission_inr.currency.upper(), "INR")
        self.assertEqual(commission_inr.source_sales_total, Decimal("150000.00"))
        self.assertEqual(commission_inr.commission_amount, Decimal("22500.00"))

    def test_explanation_uses_monthly_tier_not_per_order_lines(self):
        from commissions.commission_explanation import build_commission_explanation

        self._build_plan()
        self._order("H-E1", "30000")
        last = self._order("H-E2", "170000")
        commission = calculate_commission_for_order(last)
        data = build_commission_explanation(commission)
        keys = [line["key"] for line in data["lines"]]
        self.assertIn("commission_rate", keys)
        self.assertFalse(any(k.startswith("order_tier_") for k in keys))
        self.assertEqual(data["commission_earned"], "30000.00")
        rate_line = next(line for line in data["lines"] if line["key"] == "commission_rate")
        self.assertIn("full monthly sales total", rate_line["detail"])


class HighestRateTableAPITests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.admin_user = User.objects.create_user(
            username="highest-admin@test.com",
            password="pass12345",
            email="highest-admin@test.com",
        )
        UserProfile.objects.create(
            organization=self.org,
            email="highest-admin@test.com",
            name="Highest Admin",
            employee_id="HADM",
            role="Admin",
            enable_login=True,
        )
        self.token = Token.objects.create(user=self.admin_user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_create_clone_publish_highest_plan(self):
        create = self.client.post(
            "/api/compensation-plans/",
            {
                "plan_name": "API Highest Plan",
                "role": "Sales Rep",
                "status": "Active",
                "plan_basis": "Role",
                "effective_start_date": "2026-04-01",
                "effective_end_date": "2026-04-30",
                "commission_table_type": "HIGHEST",
                "sc_rate_tables": [
                    {
                        "tier_name": "Top",
                        "from_amount": "0",
                        "to_amount": None,
                        "commission_rate": "12",
                        "bonus_amount": "0",
                        "sequence": 1,
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        plan_id = create.data["id"]
        self.assertEqual(create.data["commission_table_type"], "HIGHEST")
        self.assertGreaterEqual(len(create.data.get("sc_rate_tables") or []), 1)

        versions = self.client.get(f"/api/compensation-plans/{plan_id}/versions/")
        self.assertEqual(versions.status_code, status.HTTP_200_OK)
        version_rows = versions.data if isinstance(versions.data, list) else versions.data["results"]
        version_id = version_rows[0]["id"]

        clone = self.client.post(f"/api/compensation-plans/{plan_id}/versions/{version_id}/clone/")
        self.assertEqual(clone.status_code, status.HTTP_201_CREATED, clone.data)
        draft_id = clone.data["id"]
        self.assertEqual(clone.data["commission_table_type"], "HIGHEST")
        self.assertGreaterEqual(len(clone.data.get("sc_rate_tables") or []), 1)

        # Avoid date overlap with the published v1 before publishing the clone.
        self.client.patch(
            f"/api/compensation-plans/{plan_id}/versions/{draft_id}/",
            {
                "effective_from": "2026-05-01",
                "effective_to": "2026-05-31",
            },
            format="json",
        )

        publish = self.client.post(
            f"/api/compensation-plans/{plan_id}/versions/{draft_id}/publish/"
        )
        self.assertEqual(publish.status_code, status.HTTP_200_OK, publish.data)
        self.assertEqual(publish.data["status"], "Published")


class MarginalRateTableTests(TestCase):
    """MARGINAL tables: a running fill level carries across the month's orders.
    Each order tops up the leftover of the band the fill level sits in (at that
    band's rate), then the rest of the order is paid at the next band's rate
    (the remainder is not capped at that band's width)."""

    def setUp(self):
        self.org = get_default_organization()
        UserProfile.objects.create(
            organization=self.org,
            email="marginal@calc.co",
            name="Marginal Rep",
            employee_id="MG1",
            role="Sales Rep",
        )

    def _build_plan(self, top_open_ended=False, with_bonus=False):
        plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Marginal Rate Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="MARGINAL",
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
            commission_table_type="MARGINAL",
        )
        top_to = None if top_open_ended else Decimal("100000")
        tiers = [
            (Decimal("0"), Decimal("10000"), Decimal("5.0"), Decimal("0")),
            (Decimal("10000"), Decimal("50000"), Decimal("10.0"), Decimal("0")),
            (
                Decimal("50000"),
                top_to,
                Decimal("15.0"),
                Decimal("300.00") if with_bonus else Decimal("0"),
            ),
        ]
        for idx, (lo, hi, rate, bonus) in enumerate(tiers, start=1):
            SCRateTable.objects.create(
                compensation_plan=plan,
                plan_version=version,
                from_amount=lo,
                to_amount=hi,
                commission_rate=rate,
                bonus_amount=bonus,
                sequence=idx,
                is_active=True,
            )
        return plan, version

    def _order(self, order_id, amount, order_date=None):
        return Order.objects.create(
            organization=self.org,
            order_id=order_id,
            employee_id="MG1",
            order_date=order_date or date(2026, 3, 10),
            sales_amount=Decimal(amount),
            order_status="Success",
            currency="INR",
        )

    def test_single_order_crosses_one_band(self):
        self._build_plan()
        # Single 59,000 order from an empty fill level crosses one boundary:
        # 10,000 @ 5% + 49,000 @ 10% = 500 + 4,900 = 5,400.
        commission = calculate_commission_for_order(self._order("M-59k", "59000"))
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("5400.00"))

    def test_user_example_fill_carries_across_orders(self):
        self._build_plan()
        # Order 1 = 9,000 -> 9,000 @ 5% = 450. Fill level now 9,000
        # (1,000 left in the 0-10k band).
        self._order("M-9k", "9000")
        # Order 2 = 50,000 -> 1,000 @ 5% (fills the band) + 49,000 @ 10%
        # = 50 + 4,900 = 4,950. Month total = 450 + 4,950 = 5,400.
        last = self._order("M-50k", "50000")
        commission = calculate_commission_for_order(last)
        self.assertEqual(commission.source_sales_total, Decimal("59000.00"))
        self.assertEqual(commission.commission_amount, Decimal("5400.00"))

    def test_within_first_band_only(self):
        self._build_plan()
        commission = calculate_commission_for_order(self._order("M-9only", "9000"))
        # 9,000 all in 0-10k @ 5% = 450
        self.assertEqual(commission.commission_amount, Decimal("450.00"))

    def test_top_band_open_ended_once_fill_reaches_it(self):
        self._build_plan(top_open_ended=True)
        # Order 1 = 60,000 -> 10,000 @ 5% + 50,000 @ 10% = 500 + 5,000 = 5,500.
        # Fill level is now 60,000 (inside the 50k+ top band).
        self._order("M-60k", "60000")
        # Order 2 = 100,000 -> whole order at the open-ended top rate 15%
        # = 15,000. Month total = 5,500 + 15,000 = 20,500.
        last = self._order("M-100k", "100000")
        commission = calculate_commission_for_order(last)
        self.assertEqual(commission.commission_amount, Decimal("20500.00"))

    def test_closed_top_band_still_extends_last_tier(self):
        # Even with a closed top band (to_amount=100000), the last tier is
        # treated as open-ended once the fill level reaches it.
        self._build_plan(top_open_ended=False)
        self._order("M-60k2", "60000")
        last = self._order("M-100k2", "100000")
        commission = calculate_commission_for_order(last)
        self.assertEqual(commission.commission_amount, Decimal("20500.00"))

    def test_bonus_added_when_order_lands_in_bonus_band(self):
        self._build_plan(with_bonus=True)
        # Order 1 = 60,000 -> 500 + 5,000 = 5,500 (lands in the 10% band, no
        # bonus there). Fill level now 60,000 (top band).
        self._order("M-b60k", "60000")
        # Order 2 = 20,000 -> whole order at top band 15% = 3,000, plus the
        # top band's 300 bonus. Month total = 5,500 + 3,300 = 8,800.
        last = self._order("M-b20k", "20000")
        commission = calculate_commission_for_order(last)
        self.assertEqual(commission.commission_amount, Decimal("8800.00"))

    def test_explanation_shows_per_order_marginal_lines(self):
        from commissions.commission_explanation import build_commission_explanation

        self._build_plan()
        self._order("M-E9k", "9000")
        last = self._order("M-E50k", "50000")
        commission = calculate_commission_for_order(last)
        data = build_commission_explanation(commission)
        keys = [line["key"] for line in data["lines"]]
        self.assertTrue(any(k.startswith("marginal_order_") for k in keys))
        self.assertFalse(any(k.startswith("order_tier_") for k in keys))
        self.assertEqual(data["commission_earned"], "5400.00")


class MarginalRateTableAPITests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.admin_user = User.objects.create_user(
            username="marginal-admin@test.com",
            password="pass12345",
            email="marginal-admin@test.com",
        )
        UserProfile.objects.create(
            organization=self.org,
            email="marginal-admin@test.com",
            name="Marginal Admin",
            employee_id="MADM",
            role="Admin",
            enable_login=True,
        )
        self.token = Token.objects.create(user=self.admin_user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_create_and_publish_marginal_plan(self):
        create = self.client.post(
            "/api/compensation-plans/",
            {
                "plan_name": "API Marginal Plan",
                "role": "Sales Rep",
                "status": "Active",
                "plan_basis": "Role",
                "effective_start_date": "2026-04-01",
                "effective_end_date": "2026-04-30",
                "commission_table_type": "MARGINAL",
                "sc_rate_tables": [
                    {
                        "tier_name": "Band 1",
                        "from_amount": "0",
                        "to_amount": "50000",
                        "commission_rate": "5",
                        "bonus_amount": "0",
                        "sequence": 1,
                        "is_active": True,
                    },
                    {
                        "tier_name": "Band 2",
                        "from_amount": "50000",
                        "to_amount": None,
                        "commission_rate": "10",
                        "bonus_amount": "0",
                        "sequence": 2,
                        "is_active": True,
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        self.assertEqual(create.data["commission_table_type"], "MARGINAL")
        self.assertGreaterEqual(len(create.data.get("sc_rate_tables") or []), 2)
