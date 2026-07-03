"""Tests for CRM order synchronization and monthly commission aggregation."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from commissions.integrations.order_sync import import_order_row, process_orders_rows
from commissions.models import CompensationPlan, Order, SCRateTable, UserProfile
from commissions.services import calculate_commission_for_order
from commissions.tenants import get_default_organization


class OrderSyncTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.rep = UserProfile.objects.create(
            organization=self.org,
            employee_id="REP-SYNC-001",
            email="sync-rep@test.com",
            name="Sync Rep",
            role="Sales Rep",
            crm_user_id="crm-owner-99",
        )
        for month_start, month_end in (
            (date(2025, 3, 1), date(2025, 3, 31)),
            (date(2025, 4, 1), date(2025, 4, 30)),
        ):
            plan = CompensationPlan.objects.create(
                organization=self.org,
                plan_name=f"Sync Test Plan {month_start:%Y-%m}",
                effective_start_date=month_start,
                effective_end_date=month_end,
                status="Active",
                role="Sales Rep",
                commission_table_type="RATE",
            )
            SCRateTable.objects.create(
                compensation_plan=plan,
                from_amount=Decimal("0"),
                to_amount=None,
                commission_rate=Decimal("10"),
                bonus_amount=Decimal("0"),
                is_active=True,
                sequence=1,
            )

    def _order_row(self, order_id, order_date, amount="1000.00"):
        return {
            "order_id": order_id,
            "order_date": order_date,
            "employee_id": self.rep.employee_id,
            "sales_amount": amount,
            "order_status": "Success",
            "currency": "USD",
            "crm_owner_id": "crm-owner-99",
        }

    def test_duplicate_crm_order_id_skipped_as_unchanged(self):
        row = self._order_row("CRM-DEAL-1", "2025-03-05")
        first = import_order_row(self.org, row, crm_provider="hubspot")
        second = import_order_row(self.org, row, crm_provider="hubspot")

        self.assertEqual(first["action"], "created")
        self.assertEqual(second["action"], "unchanged")
        self.assertEqual(
            Order.objects.filter(organization=self.org, order_id="CRM-DEAL-1").count(),
            1,
        )

    def test_multiple_orders_same_employee_different_dates_stored_separately(self):
        rows = [
            self._order_row("CRM-DEAL-A", "2025-03-01", "500.00"),
            self._order_row("CRM-DEAL-B", "2025-03-15", "700.00"),
            self._order_row("CRM-DEAL-C", "2025-04-02", "300.00"),
        ]
        result = process_orders_rows(self.org, rows, crm_provider="salesforce")
        self.assertEqual(result["created"], 3)
        self.assertEqual(
            Order.objects.filter(
                organization=self.org,
                employee_id=self.rep.employee_id,
            ).count(),
            3,
        )
        dates = set(
            Order.objects.filter(organization=self.org).values_list("order_date", flat=True)
        )
        self.assertEqual(
            dates,
            {date(2025, 3, 1), date(2025, 3, 15), date(2025, 4, 2)},
        )

    def test_late_sync_in_same_month_recalculates_monthly_commission(self):
        row1 = self._order_row("CRM-MONTH-1", "2025-03-10", "1000.00")
        row2 = self._order_row("CRM-MONTH-2", "2025-03-20", "500.00")

        process_orders_rows(self.org, [row1], crm_provider="hubspot")
        commission_after_first = calculate_commission_for_order(
            Order.objects.get(order_id="CRM-MONTH-1")
        )
        self.assertIsNotNone(commission_after_first)
        self.assertEqual(commission_after_first.source_order_count, 1)
        self.assertEqual(commission_after_first.source_sales_total, Decimal("1000.00"))

        process_orders_rows(self.org, [row2], crm_provider="hubspot")
        commission_after_second = calculate_commission_for_order(
            Order.objects.get(order_id="CRM-MONTH-2")
        )
        self.assertIsNotNone(commission_after_second)
        self.assertEqual(commission_after_second.source_order_count, 2)
        self.assertEqual(commission_after_second.source_sales_total, Decimal("1500.00"))

    def test_crm_metadata_persisted_on_order(self):
        row = self._order_row("CRM-META-1", "2025-03-01")
        import_order_row(self.org, row, crm_provider="zoho")
        order = Order.objects.get(order_id="CRM-META-1")
        self.assertEqual(order.crm_provider, "zoho")
        self.assertEqual(order.crm_owner_id, "crm-owner-99")
        self.assertEqual(order.order_date, date(2025, 3, 1))

    def test_usd_import_sets_usa_business_group_even_for_india_rep(self):
        self.rep.business_group = "India"
        self.rep.personal_currency = "INR"
        self.rep.save(update_fields=["business_group", "personal_currency"])
        row = self._order_row("CRM-USD-BG", "2025-03-01")
        import_order_row(self.org, row, crm_provider="hubspot")
        order = Order.objects.get(order_id="CRM-USD-BG")
        self.assertEqual(order.currency, "USD")
        self.assertEqual(order.business_group, "USA")

    def test_updated_crm_order_changes_amount_and_recalculates(self):
        row = self._order_row("CRM-UPD-1", "2025-03-05", "1000.00")
        process_orders_rows(self.org, [row], crm_provider="hubspot")
        order = Order.objects.get(order_id="CRM-UPD-1")
        first_commission = calculate_commission_for_order(order)
        self.assertEqual(first_commission.commission_amount, Decimal("100.00"))

        updated = self._order_row("CRM-UPD-1", "2025-03-05", "2000.00")
        result = process_orders_rows(self.org, [updated], crm_provider="hubspot")
        self.assertEqual(result["updated"], 1)
        order.refresh_from_db()
        self.assertEqual(order.sales_amount, Decimal("2000.00"))
        second_commission = calculate_commission_for_order(order)
        self.assertEqual(second_commission.commission_amount, Decimal("200.00"))
