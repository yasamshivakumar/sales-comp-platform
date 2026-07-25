"""Tests for employee compensation overrides and rule hierarchy."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from commissions.commission_rules import (
    build_rule_context,
    evaluate_rule_conditions,
)
from commissions.compensation_overrides import apply_employee_overrides
from commissions.models import (
    CommissionRule,
    CommissionRuleCondition,
    CompensationPlan,
    EmployeeCompensationOverride,
    Organization,
    UserProfile,
)

User = get_user_model()


class OverrideApplicationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Override Org")
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Sales Rep Plan",
            status="Active",
            commission_table_type="RATE",
            role="Sales Rep",
            effective_start_date=date(2026, 1, 1),
        )
        self.profile = UserProfile.objects.create(
            organization=self.org,
            name="Ramya",
            email="ramya@example.com",
            employee_id="E-RAMYA",
            role="Sales Rep",
            assigned_compensation_plan=self.plan,
            personal_target=Decimal("100000"),
        )
        self.order = SimpleNamespace(
            sales_amount=Decimal("10000"),
            order_date=date(2026, 2, 15),
            region="West",
            product_name="Widget",
            service_name="Widgets",
            distribution="Direct",
            customer_segment="Enterprise",
            business_group="USA",
            order_status="Success",
            currency="USD",
            position_name="Sales Rep",
            employee_id="E-RAMYA",
            territory=None,
            margin=None,
        )

    def _override(self, **kwargs):
        defaults = dict(
            organization=self.org,
            employee=self.profile,
            compensation_plan=self.plan,
            name="Ramya Override",
            override_type=EmployeeCompensationOverride.TYPE_COMMISSION_RATE,
            value=Decimal("3"),
            value_unit=EmployeeCompensationOverride.UNIT_PERCENT,
            previous_value=Decimal("2"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 3, 31),
            reason="Promotion Incentive",
            status=EmployeeCompensationOverride.STATUS_APPROVED,
            stop_on_match=True,
        )
        defaults.update(kwargs)
        return EmployeeCompensationOverride.objects.create(**defaults)

    def test_rate_override_replaces_plan_base(self):
        self._override()
        amount, applied, suppress, trace = apply_employee_overrides(
            self.profile,
            self.order,
            base_amount=Decimal("200"),  # plan 2% of 10k
            sales_amount=Decimal("10000"),
            on_date=date(2026, 2, 15),
            plan=self.plan,
        )
        self.assertEqual(amount, Decimal("300"))  # 3% of 10k
        self.assertTrue(suppress)
        self.assertEqual(applied.name, "Ramya Override")
        self.assertTrue(trace["applied"])

    def test_override_outside_window_ignored(self):
        self._override()
        amount, applied, suppress, _ = apply_employee_overrides(
            self.profile,
            self.order,
            base_amount=Decimal("200"),
            sales_amount=Decimal("10000"),
            on_date=date(2026, 6, 1),
            plan=self.plan,
        )
        self.assertEqual(amount, Decimal("200"))
        self.assertIsNone(applied)
        self.assertFalse(suppress)

    def test_draft_override_ignored(self):
        self._override(status=EmployeeCompensationOverride.STATUS_DRAFT)
        amount, applied, _, _ = apply_employee_overrides(
            self.profile,
            self.order,
            base_amount=Decimal("200"),
            sales_amount=Decimal("10000"),
            on_date=date(2026, 2, 15),
            plan=self.plan,
        )
        self.assertEqual(amount, Decimal("200"))
        self.assertIsNone(applied)

    def test_multiplier_stacks_after_rate(self):
        self._override()
        self._override(
            name="Accelerator",
            override_type=EmployeeCompensationOverride.TYPE_MULTIPLIER,
            value=Decimal("1.5"),
            value_unit=EmployeeCompensationOverride.UNIT_MULTIPLIER,
            stop_on_match=False,
        )
        amount, applied, suppress, _ = apply_employee_overrides(
            self.profile,
            self.order,
            base_amount=Decimal("200"),
            sales_amount=Decimal("10000"),
            on_date=date(2026, 2, 15),
            plan=self.plan,
        )
        self.assertEqual(amount, Decimal("450"))  # 300 * 1.5
        self.assertEqual(applied.override_type, "commission_rate")
        self.assertTrue(suppress)


class RuleConditionLogicTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Rule Org")
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Plan",
            status="Active",
            commission_table_type="RATE",
            effective_start_date=date(2026, 1, 1),
        )
        self.rule = CommissionRule.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            name="Territory OR Role",
            scope=CommissionRule.SCOPE_TERRITORY,
            priority=2,
            condition_logic=CommissionRule.LOGIC_OR,
        )
        CommissionRuleCondition.objects.create(
            rule=self.rule, field="region", operator="eq", value="West", sequence=1
        )
        CommissionRuleCondition.objects.create(
            rule=self.rule, field="role", operator="eq", value="Manager", sequence=2
        )
        self.profile = UserProfile.objects.create(
            organization=self.org,
            name="Alex",
            email="alex@example.com",
            employee_id="E1",
            role="Sales Rep",
        )
        self.order = SimpleNamespace(
            sales_amount=Decimal("5000"),
            order_date=date(2026, 2, 1),
            region="West",
            product_name="",
            service_name="",
            distribution="",
            customer_segment="",
            business_group="",
            order_status="Success",
            currency="USD",
            position_name="",
            employee_id="E1",
            territory=None,
            margin=None,
        )

    def test_or_logic_matches_any_condition(self):
        context = build_rule_context(self.order, self.profile, self.plan)
        self.assertTrue(evaluate_rule_conditions(self.rule, context))

    def test_and_logic_requires_all(self):
        self.rule.condition_logic = CommissionRule.LOGIC_AND
        self.rule.save(update_fields=["condition_logic"])
        context = build_rule_context(self.order, self.profile, self.plan)
        self.assertFalse(evaluate_rule_conditions(self.rule, context))

    def test_achievement_pct_numeric_condition(self):
        rule = CommissionRule.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            name="Over quota",
            scope=CommissionRule.SCOPE_PLAN_DEFAULT,
            priority=5,
            condition_logic=CommissionRule.LOGIC_AND,
        )
        CommissionRuleCondition.objects.create(
            rule=rule,
            field="achievement_pct",
            operator="gte",
            value="50",
        )
        self.profile.personal_target = Decimal("10000")
        self.profile.save(update_fields=["personal_target"])
        context = build_rule_context(self.order, self.profile, self.plan)
        # 5000 / 10000 = 50%
        self.assertTrue(evaluate_rule_conditions(rule, context))
