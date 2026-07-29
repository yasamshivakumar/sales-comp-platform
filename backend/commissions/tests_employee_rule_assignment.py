"""Employee-specific commission rule assignment tests."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from commissions.commission_rules import apply_commission_rules
from commissions.models import (
    CommissionRule,
    CommissionRuleCondition,
    CommissionRuleResult,
    CompensationPlan,
    EmployeeCommissionRuleAssignment,
    Order,
    Organization,
    SCRateTable,
    UserProfile,
)
from commissions.rule_assignments import (
    add_rule_assignments,
    find_invalid_assignments,
    remove_rule_assignments,
    sync_rule_assignments,
    validate_employees_for_rule,
    valid_assigned_rule_ids_for_employee,
)
from commissions.rule_views import (
    commission_rule_eligible_employees,
    commission_rule_employees,
    commission_rule_invalid_assignments,
    employee_commission_rules,
)
from commissions.services import calculate_commission_for_order, recalculate_orders_in_range

User = get_user_model()


class EmployeeRuleAssignmentTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Rule Assign Org", slug="rule-assign-org")
        self.other_org = Organization.objects.create(name="Other Org", slug="other-org-rules")
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Shared Plan",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
        )
        self.other_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Other Plan",
            status="Active",
            role="Manager",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("5"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )
        self.alice = UserProfile.objects.create(
            organization=self.org,
            name="Alice",
            email="alice@example.com",
            employee_id="E-ALICE",
            role="Sales Rep",
            assigned_compensation_plan=self.plan,
        )
        self.bob = UserProfile.objects.create(
            organization=self.org,
            name="Bob",
            email="bob@example.com",
            employee_id="E-BOB",
            role="Sales Rep",
            assigned_compensation_plan=self.plan,
        )
        self.carol_other_plan = UserProfile.objects.create(
            organization=self.org,
            name="Carol",
            email="carol@example.com",
            employee_id="E-CAROL",
            role="Manager",
            assigned_compensation_plan=self.other_plan,
        )
        self.outsider = UserProfile.objects.create(
            organization=self.other_org,
            name="Outsider",
            email="out@example.com",
            employee_id="E-OUT",
            role="Sales Rep",
        )
        self.rule = CommissionRule.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            name="Alice bonus",
            rule_type="commission_rate",
            sequence=1,
            is_active=True,
        )
        CommissionRuleCondition.objects.create(
            rule=self.rule,
            field="product_name",
            operator="eq",
            value="Enterprise",
            sequence=1,
        )
        CommissionRuleResult.objects.create(
            rule=self.rule,
            result_name="Bonus",
            result_rate_type="add_bonus",
            rate_value=Decimal("500"),
            sequence=1,
        )
        self.admin = User.objects.create_user(
            username="rule-admin", password="pass", email="admin@example.com"
        )
        self.admin.is_staff = True
        self.admin.save()
        UserProfile.objects.create(
            organization=self.org,
            email=self.admin.email,
            username=self.admin.username,
            name="Admin",
            employee_id="E-ADMIN",
            role="Admin",
            enable_login=True,
        )
        self.factory = APIRequestFactory()

    def test_sync_and_remove_assignments(self):
        added, removed, current = sync_rule_assignments(
            self.rule, [self.alice.id], organization=self.org
        )
        self.assertEqual(added, 1)
        self.assertEqual(removed, 0)
        self.assertEqual(current, [self.alice.id])
        self.assertEqual(
            EmployeeCommissionRuleAssignment.objects.filter(rule=self.rule).count(), 1
        )

        added = add_rule_assignments(
            self.rule, [self.bob.id, self.alice.id], organization=self.org
        )
        self.assertEqual(added, [self.bob.id])
        self.assertEqual(
            EmployeeCommissionRuleAssignment.objects.filter(rule=self.rule).count(), 2
        )

        removed = remove_rule_assignments(self.rule, [self.alice.id])
        self.assertEqual(removed, 1)
        self.assertEqual(
            list(
                EmployeeCommissionRuleAssignment.objects.filter(rule=self.rule).values_list(
                    "employee_id", flat=True
                )
            ),
            [self.bob.id],
        )

    def test_rejects_other_org_and_plan_mismatch(self):
        with self.assertRaises(ValidationError):
            validate_employees_for_rule(
                self.rule, [self.outsider.id], organization=self.org
            )
        with self.assertRaises(ValidationError):
            validate_employees_for_rule(
                self.rule, [self.carol_other_plan.id], organization=self.org
            )

    def test_calc_only_assigned_employee_gets_rule(self):
        EmployeeCommissionRuleAssignment.objects.create(
            organization=self.org, employee=self.alice, rule=self.rule
        )

        alice_order = Order.objects.create(
            organization=self.org,
            order_id="ORD-ALICE",
            order_date=date(2026, 2, 1),
            employee_id="E-ALICE",
            product_name="Enterprise",
            sales_amount=Decimal("10000"),
            order_status="Success",
        )
        bob_order = Order.objects.create(
            organization=self.org,
            order_id="ORD-BOB",
            order_date=date(2026, 2, 1),
            employee_id="E-BOB",
            product_name="Enterprise",
            sales_amount=Decimal("10000"),
            order_status="Success",
        )

        alice_c = calculate_commission_for_order(alice_order)
        bob_c = calculate_commission_for_order(bob_order)

        self.assertIsNotNone(alice_c)
        self.assertEqual(alice_c.commission_amount, Decimal("1000.00"))
        self.assertEqual(alice_c.commission_rule_id, self.rule.id)

        self.assertIsNotNone(bob_c)
        # Base 5% only — no bonus rule
        self.assertEqual(bob_c.commission_amount, Decimal("500.00"))
        self.assertIsNone(bob_c.commission_rule_id)

    def test_apply_commission_rules_empty_without_assignment(self):
        order = type(
            "O",
            (),
            {
                "sales_amount": Decimal("10000"),
                "order_date": date(2026, 2, 1),
                "product_name": "Enterprise",
            },
        )()
        amount, _, matched, _ = apply_commission_rules(
            self.plan, order, self.bob, Decimal("500")
        )
        self.assertEqual(amount, Decimal("500"))
        self.assertIsNone(matched)

    def test_recalculate_scoped_to_employee(self):
        EmployeeCommissionRuleAssignment.objects.create(
            organization=self.org, employee=self.alice, rule=self.rule
        )
        Order.objects.create(
            organization=self.org,
            order_id="ORD-ALICE-2",
            order_date=date(2026, 2, 10),
            employee_id="E-ALICE",
            product_name="Enterprise",
            sales_amount=Decimal("10000"),
            order_status="Success",
        )
        Order.objects.create(
            organization=self.org,
            order_id="ORD-BOB-2",
            order_date=date(2026, 2, 10),
            employee_id="E-BOB",
            product_name="Enterprise",
            sales_amount=Decimal("10000"),
            order_status="Success",
        )
        result = recalculate_orders_in_range(
            date(2026, 2, 1),
            date(2026, 2, 28),
            employee_q="E-ALICE",
            organization=self.org,
            force=True,
        )
        self.assertGreaterEqual(result.get("processed", 0), 1)
        self.assertEqual(result.get("order_count"), 1)

        alice_order = Order.objects.get(order_id="ORD-ALICE-2")
        bob_order = Order.objects.get(order_id="ORD-BOB-2")
        alice_c = calculate_commission_for_order(alice_order, force=True)
        bob_c = calculate_commission_for_order(bob_order, force=True)
        self.assertEqual(alice_c.commission_amount, Decimal("1000.00"))
        self.assertEqual(bob_c.commission_amount, Decimal("500.00"))
        self.assertIsNone(bob_c.commission_rule_id)

    def test_api_assign_list_and_employee_rules(self):
        request = self.factory.post(
            f"/api/commission-rules/{self.rule.id}/employees/",
            {"employee_ids": [self.alice.id]},
            format="json",
        )
        request.organization = self.org
        force_authenticate(request, user=self.admin)

        response = commission_rule_employees(request, pk=self.rule.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.alice.id, response.data.get("added", []))

        get_req = self.factory.get(f"/api/commission-rules/{self.rule.id}/employees/")
        get_req.organization = self.org
        force_authenticate(get_req, user=self.admin)
        listed = commission_rule_employees(get_req, pk=self.rule.id)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)

        emp_req = self.factory.get(f"/api/user-setup/{self.alice.id}/commission-rules/")
        emp_req.organization = self.org
        force_authenticate(emp_req, user=self.admin)
        emp_rules = employee_commission_rules(emp_req, pk=self.alice.id)
        self.assertEqual(emp_rules.status_code, 200)
        results = emp_rules.data.get("results", emp_rules.data)
        self.assertEqual(results[0]["id"], self.rule.id)
        self.assertEqual(results[0]["compensation_plan_name"], self.plan.plan_name)

        alias_req = self.factory.get(
            f"/api/employees/{self.alice.id}/commission-rules/"
        )
        alias_req.organization = self.org
        force_authenticate(alias_req, user=self.admin)
        alias = employee_commission_rules(alias_req, pk=self.alice.id)
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.data["count"], 1)

    def test_api_rejects_cross_tenant(self):
        request = self.factory.post(
            f"/api/commission-rules/{self.rule.id}/employees/",
            {"employee_ids": [self.outsider.id]},
            format="json",
        )
        request.organization = self.org
        force_authenticate(request, user=self.admin)
        response = commission_rule_employees(request, pk=self.rule.id)
        self.assertEqual(response.status_code, 400)

    def test_api_rejects_other_plan_employee(self):
        request = self.factory.post(
            f"/api/commission-rules/{self.rule.id}/employees/",
            {"employee_ids": [self.carol_other_plan.id]},
            format="json",
        )
        request.organization = self.org
        force_authenticate(request, user=self.admin)
        response = commission_rule_employees(request, pk=self.rule.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("employee_ids", response.data)

    def test_eligible_employees_filtered_by_plan_and_org(self):
        unassigned = UserProfile.objects.create(
            organization=self.org,
            name="Dana",
            email="dana@example.com",
            employee_id="E-DANA",
            role="Sales Rep",
            assigned_compensation_plan=None,
        )
        req = self.factory.get(
            f"/api/commission-rules/eligible-employees/?plan_id={self.plan.id}"
        )
        req.organization = self.org
        force_authenticate(req, user=self.admin)
        res = commission_rule_eligible_employees(req)
        self.assertEqual(res.status_code, 200)
        results = res.data.get("results", res.data)
        ids = {row["id"] for row in results}
        self.assertIn(self.alice.id, ids)
        self.assertIn(self.bob.id, ids)
        # Unassigned role match appears when People would resolve them to this plan.
        self.assertIn(unassigned.id, ids)
        self.assertNotIn(self.carol_other_plan.id, ids)
        self.assertNotIn(self.outsider.id, ids)

        other_req = self.factory.get(
            f"/api/commission-rules/eligible-employees/?plan_id={self.other_plan.id}"
        )
        other_req.organization = self.org
        force_authenticate(other_req, user=self.admin)
        other_res = commission_rule_eligible_employees(other_req)
        other_ids = {row["id"] for row in other_res.data["results"]}
        self.assertIn(self.carol_other_plan.id, other_ids)
        self.assertNotIn(self.alice.id, other_ids)
        self.assertNotIn(self.bob.id, other_ids)
        self.assertNotIn(unassigned.id, other_ids)

    def test_sibling_role_plan_does_not_duplicate_unassigned(self):
        """Second plan with same role must not list people who resolve to the first."""
        sibling = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Sales Reps Twin",
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
        )
        unassigned = UserProfile.objects.create(
            organization=self.org,
            name="Dana Twin",
            email="danatwin@example.com",
            employee_id="E-DANA-TWIN",
            role="Sales Rep",
            assigned_compensation_plan=None,
        )
        # Primary plan (self.plan, created first) is the resolve winner.
        primary = self.factory.get(
            f"/api/commission-rules/eligible-employees/?plan_id={self.plan.id}"
        )
        primary.organization = self.org
        force_authenticate(primary, user=self.admin)
        primary_ids = {
            row["id"]
            for row in commission_rule_eligible_employees(primary).data["results"]
        }
        self.assertIn(unassigned.id, primary_ids)

        twin = self.factory.get(
            f"/api/commission-rules/eligible-employees/?plan_id={sibling.id}"
        )
        twin.organization = self.org
        force_authenticate(twin, user=self.admin)
        twin_ids = {
            row["id"] for row in commission_rule_eligible_employees(twin).data["results"]
        }
        self.assertNotIn(unassigned.id, twin_ids)
        self.assertNotIn(self.alice.id, twin_ids)

    def test_saving_rule_assigns_unassigned_employee_to_plan(self):
        unassigned = UserProfile.objects.create(
            organization=self.org,
            name="Dana",
            email="dana2@example.com",
            employee_id="E-DANA2",
            role="Sales Rep",
            assigned_compensation_plan=None,
        )
        sync_rule_assignments(self.rule, [unassigned.id], organization=self.org)
        unassigned.refresh_from_db()
        self.assertEqual(unassigned.assigned_compensation_plan_id, self.plan.id)

    def test_sync_requires_at_least_one_employee(self):
        with self.assertRaises(ValidationError):
            sync_rule_assignments(self.rule, [], organization=self.org)

    def test_invalid_assignments_detected_and_ignored_in_calc(self):
        # Carol is on other_plan but wrongly linked to this rule
        EmployeeCommissionRuleAssignment.objects.create(
            organization=self.org,
            employee=self.carol_other_plan,
            rule=self.rule,
        )
        invalid = find_invalid_assignments(organization=self.org)
        self.assertTrue(
            any(row["employee_id"] == self.carol_other_plan.id for row in invalid)
        )

        report_req = self.factory.get("/api/commission-rules/invalid-assignments/")
        report_req.organization = self.org
        force_authenticate(report_req, user=self.admin)
        report = commission_rule_invalid_assignments(report_req)
        self.assertEqual(report.status_code, 200)
        self.assertGreaterEqual(report.data["count"], 1)

        # Invalid assignment must not drive calculation
        self.assertFalse(
            valid_assigned_rule_ids_for_employee(self.carol_other_plan).exists()
        )

        carol_order = Order.objects.create(
            organization=self.org,
            order_id="ORD-CAROL-BAD",
            order_date=date(2026, 2, 1),
            employee_id="E-CAROL",
            product_name="Enterprise",
            sales_amount=Decimal("10000"),
            order_status="Success",
        )
        # Carol is on other_plan — calc uses her plan, not this rule
        carol_c = calculate_commission_for_order(carol_order)
        # No rate table on other_plan — may be None or zero; rule must not apply
        if carol_c is not None:
            self.assertNotEqual(carol_c.commission_rule_id, self.rule.id)

    def test_requires_plan_before_assign(self):
        orphan = CommissionRule.objects.create(
            organization=self.org,
            compensation_plan=None,
            name="No plan rule",
            rule_type="commission_rate",
            sequence=99,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            validate_employees_for_rule(
                orphan, [self.alice.id], organization=self.org
            )

    def test_apply_to_all_plan_participants_includes_future_members(self):
        """Plan-wide rules apply without explicit assignment and pick up new members."""
        from commissions.compensation_overrides import assigned_rules_for_employee_display

        self.rule.apply_to_all_plan_participants = True
        self.rule.save(update_fields=["apply_to_all_plan_participants"])
        EmployeeCommissionRuleAssignment.objects.filter(rule=self.rule).delete()

        # Existing plan members see the rule without an assignment row.
        self.assertTrue(
            valid_assigned_rule_ids_for_employee(self.alice).filter(id=self.rule.id).exists()
        )
        self.assertTrue(
            valid_assigned_rule_ids_for_employee(self.bob).filter(id=self.rule.id).exists()
        )
        # Other-plan employee does not.
        self.assertFalse(
            valid_assigned_rule_ids_for_employee(self.carol_other_plan)
            .filter(id=self.rule.id)
            .exists()
        )

        names = {
            row["name"]
            for row in assigned_rules_for_employee_display(self.alice, organization=self.org)
        }
        self.assertIn(self.rule.name, names)

        # New participant joining the plan later gets the rule automatically.
        newbie = UserProfile.objects.create(
            organization=self.org,
            name="Eve",
            email="eve@example.com",
            employee_id="E-EVE",
            role="Sales Rep",
            assigned_compensation_plan=self.plan,
        )
        self.assertTrue(
            valid_assigned_rule_ids_for_employee(newbie).filter(id=self.rule.id).exists()
        )
        newbie_names = {
            row["name"]
            for row in assigned_rules_for_employee_display(newbie, organization=self.org)
        }
        self.assertIn(self.rule.name, newbie_names)