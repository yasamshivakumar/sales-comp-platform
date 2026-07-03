from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from commissions.business_groups import (
    apply_business_group_to_commissions,
    apply_business_group_to_orders,
)
from commissions.models import (
    Commission,
    Employee,
    Order,
    Organization,
    Sale,
    UserProfile,
)


class BusinessGroupFilterTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="BG Co", slug="bg-co")
        self.admin = User.objects.create_user(
            username="bg-admin",
            email="bg-admin@test.com",
            password="Pass12345",
        )
        UserProfile.objects.create(
            organization=self.org,
            email=self.admin.email,
            employee_id="BG-ADMIN",
            name="BG Admin",
            role="Admin",
            business_group="India",
            enable_login=True,
        )
        self.india_rep = User.objects.create_user(
            username="india-rep",
            email="india-rep@test.com",
            password="Pass12345",
        )
        UserProfile.objects.create(
            organization=self.org,
            email=self.india_rep.email,
            employee_id="IN-001",
            name="India Rep",
            role="Sales Rep",
            business_group="India",
            personal_currency="INR",
            enable_login=True,
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            name="India Rep",
            email="india-rep@test.com",
        )
        self.usd_order = Order.objects.create(
            organization=self.org,
            order_id="USD-100",
            order_date="2026-06-15",
            employee_id="IN-001",
            sales_amount=Decimal("10000.00"),
            order_status="Success",
            currency="USD",
            business_group="",
        )
        self.inr_order = Order.objects.create(
            organization=self.org,
            order_id="INR-100",
            order_date="2026-06-16",
            employee_id="IN-001",
            sales_amount=Decimal("50000.00"),
            order_status="Success",
            currency="INR",
            business_group="",
        )
        sale = Sale.objects.create(
            organization=self.org,
            order=None,
            employee=self.employee,
            employee_salary=Decimal("0.00"),
            amount=Decimal("10000.00"),
        )
        self.usd_commission = Commission.objects.create(
            organization=self.org,
            employee=self.employee,
            sale=sale,
            commission_amount=Decimal("500.00"),
            currency="USD",
            calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH,
            period_start="2026-06-01",
            period_end="2026-06-30",
        )
        self.client = APIClient()
        token = Token.objects.create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_usd_order_matches_usa_not_india(self):
        orders = Order.objects.filter(organization=self.org)
        usa = apply_business_group_to_orders(orders, "USA", organization=self.org)
        india = apply_business_group_to_orders(orders, "India", organization=self.org)

        self.assertIn(self.usd_order, usa)
        self.assertNotIn(self.usd_order, india)
        self.assertIn(self.inr_order, india)
        self.assertNotIn(self.inr_order, usa)

    def test_usd_commission_matches_usa_not_india(self):
        commissions = Commission.objects.filter(organization=self.org)
        usa = apply_business_group_to_commissions(
            commissions, "USA", organization=self.org
        )
        india = apply_business_group_to_commissions(
            commissions, "India", organization=self.org
        )

        self.assertIn(self.usd_commission, usa)
        self.assertNotIn(self.usd_commission, india)

    def test_dashboard_summary_respects_usa_filter(self):
        response = self.client.get(
            "/api/reports/commission-summary/?business_group=USA"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(float(payload["total_commission"]), 500.0)
        self.assertEqual(payload["totals_by_currency"][0]["currency"], "USD")

    def test_dashboard_summary_india_excludes_usd(self):
        response = self.client.get(
            "/api/reports/commission-summary/?business_group=India"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(float(payload["total_commission"]), 0.0)

    def test_sales_performance_respects_usa_filter(self):
        response = self.client.get(
            "/api/reports/sales-performance/?business_group=USA"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(float(payload["total_sales"]), 10000.0)
        self.assertEqual(payload["totals_by_currency"][0]["currency"], "USD")
