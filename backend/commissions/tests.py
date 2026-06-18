from decimal import Decimal
from datetime import date
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.authtoken.models import Token

from .tenants import get_default_organization
from .models import (
    UserProfile,
    CompensationPlan,
    SCRateTable,
    SCLookupTable,
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
    find_sc_lookup_tier,
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
            order_status="Success",
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

    def test_resolve_role_plan_case_insensitive(self):
        self.rep.role = "sales rep"
        self.rep.save(update_fields=["role"])
        order = self._order(
            "O-ROLE-LOWER",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        plan, source = resolve_compensation_plan(order)
        self.assertEqual(plan, self.role_plan)
        self.assertEqual(source, "role:sales rep")

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
            plan_name="Rep Plan 2025 Jan",
            effective_start_date=date(2025, 1, 1),
            effective_end_date=date(2025, 1, 31),
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
            plan_name="Rep Plan 2025 Aug",
            effective_start_date=date(2025, 8, 1),
            effective_end_date=date(2025, 8, 31),
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
        order_h1.order_date = date(2025, 1, 15)
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

        order_march = self._order(
            "O-MAR",
            "REP001",
            "10000",
            position_name="Standard Rep Position",
        )
        order_march.order_date = date(2025, 3, 15)
        order_march.save()
        plan_march, _ = resolve_compensation_plan(order_march)
        self.assertIsNone(plan_march)

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


class CommissionRuleEngineTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.start = date(2025, 1, 1)
        UserProfile.objects.create(
            organization=self.org,
            employee_id="RULE001",
            email="rule@test.com",
            name="Rule Rep",
            role="Sales Rep",
        )
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Rule Test Plan",
            effective_start_date=self.start,
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
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

    def test_product_condition_applies_bonus_result(self):
        from .models import CommissionRule, CommissionRuleCondition, CommissionRuleResult

        rule = CommissionRule.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            name="Enterprise bonus",
            rule_type="commission_rate",
            sequence=1,
        )
        CommissionRuleCondition.objects.create(
            rule=rule,
            field="product_name",
            operator="eq",
            value="Enterprise",
            sequence=1,
        )
        CommissionRuleResult.objects.create(
            rule=rule,
            result_name="Bonus",
            result_rate_type="add_bonus",
            rate_value=Decimal("500"),
            sequence=1,
        )

        order = Order.objects.create(
            organization=self.org,
            order_id="RULE-ORD-1",
            order_date=self.start,
            employee_id="RULE001",
            product_name="Enterprise",
            sales_amount=Decimal("10000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("1000.00"))
        self.assertEqual(commission.commission_rule_id, rule.id)
        self.assertEqual(commission.rule_result_name, "Bonus")

    def test_override_tier_pct_replaces_plan_rate(self):
        from .models import CommissionRule, CommissionRuleCondition, CommissionRuleResult

        rule = CommissionRule.objects.create(
            organization=self.org,
            compensation_plan=self.plan,
            name="SaaS override rate",
            rule_type="commission_rate",
            sequence=1,
        )
        CommissionRuleCondition.objects.create(
            rule=rule,
            field="product_name",
            operator="eq",
            value="saas",
            sequence=1,
        )
        CommissionRuleResult.objects.create(
            rule=rule,
            result_name="SaaS rate",
            result_rate_type="override_tier_pct",
            rate_value=Decimal("2.5"),
            sequence=1,
        )

        order = Order.objects.create(
            organization=self.org,
            order_id="RULE-ORD-2",
            order_date=self.start,
            employee_id="RULE001",
            product_name="saas",
            sales_amount=Decimal("100000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        # 2.5% of 100000 = 2500, not plan tier 5% = 5000
        self.assertEqual(commission.commission_amount, Decimal("2500.00"))
        self.assertEqual(commission.commission_rule_id, rule.id)


class CommissionExplanationTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.start = date(2025, 1, 1)
        UserProfile.objects.create(
            organization=self.org,
            employee_id="EXP001",
            email="exp@test.com",
            name="Explain Rep",
            role="Sales Rep",
        )
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Explain Plan",
            effective_start_date=self.start,
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
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

    def test_explanation_includes_tier_breakdown(self):
        from .commission_explanation import build_commission_explanation

        order = Order.objects.create(
            organization=self.org,
            order_id="EXP-ORD-1",
            order_date=self.start,
            employee_id="EXP001",
            sales_amount=Decimal("120000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        data = build_commission_explanation(commission)
        self.assertEqual(data["commission_earned"], "6000.00")
        keys = [line["key"] for line in data["lines"]]
        self.assertIn("order_value", keys)
        self.assertIn("commission_rate", keys)
        self.assertIn("final_commission", keys)

    def test_what_if_simulator_parses_string_dates(self):
        from .commission_explanation import simulate_what_if
        from django.contrib.auth.models import User

        user = User.objects.create_user(
            username="exp@test.com",
            email="exp@test.com",
            password="test",
        )
        request = type("Req", (), {"user": user})()
        data = simulate_what_if(request, Decimal("50000"), "2025-01-01", "2025-01-31")
        self.assertNotIn("error", data)
        self.assertIn("projected_commission", data)
        self.assertEqual(data["projected_commission"], "2500.00")

    @override_settings(COMMISSION_AI_API_KEY="test-key", COMMISSION_AI_ENABLED=True)
    def test_ask_answers_open_ended_quota_question(self):
        from .commission_explanation import answer_commission_question
        from django.contrib.auth.models import User

        UserProfile.objects.filter(email="exp@test.com").update(
            personal_target=Decimal("100000")
        )
        order = Order.objects.create(
            organization=self.org,
            order_id="EXP-ORD-2",
            order_date=self.start,
            employee_id="EXP001",
            sales_amount=Decimal("50000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        user = User.objects.create_user(
            username="exp@test.com",
            email="exp@test.com",
            password="test",
        )
        request = type("Req", (), {"user": user})()
        with patch(
            "commissions.commission_ai._call_chat_completion",
            return_value="Your quota target is ₹100,000 and you are at 50% attainment.",
        ):
            data = answer_commission_question(
                commission, "What is my quota progress this month?", request
            )
        self.assertIn("target", data["answer"].lower())
        self.assertEqual(data.get("source"), "ai")

    @override_settings(COMMISSION_AI_API_KEY="test-key", COMMISSION_AI_ENABLED=True)
    def test_ask_answers_unusual_question_with_context(self):
        from .commission_explanation import answer_commission_question
        from django.contrib.auth.models import User

        order = Order.objects.create(
            organization=self.org,
            order_id="EXP-ORD-3",
            order_date=self.start,
            employee_id="EXP001",
            sales_amount=Decimal("80000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        user = User.objects.create_user(
            username="exp3@test.com",
            email="exp@test.com",
            password="test",
        )
        request = type("Req", (), {"user": user})()
        with patch(
            "commissions.commission_ai._call_chat_completion",
            return_value="The tier rate on this deal is 5% on ₹80,000 order value.",
        ):
            data = answer_commission_question(
                commission, "Tell me about the tier rate on this deal", request
            )
        self.assertIn("rate", data["answer"].lower())
        self.assertEqual(data.get("source"), "ai")

    @override_settings(COMMISSION_AI_API_KEY="test-key", COMMISSION_AI_ENABLED=True)
    def test_ask_how_are_you_goes_to_llm(self):
        from .commission_explanation import answer_commission_question
        from django.contrib.auth.models import User

        order = Order.objects.create(
            organization=self.org,
            order_id="EXP-ORD-CASUAL",
            order_date=self.start,
            employee_id="EXP001",
            sales_amount=Decimal("80000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        user = User.objects.create_user(
            username="exp_casual@test.com",
            email="exp@test.com",
            password="test",
        )
        request = type("Req", (), {"user": user})()
        with patch(
            "commissions.commission_ai._call_chat_completion",
            return_value="I'm doing well! You're looking at ₹4,000 on this order — ask me anything about it.",
        ) as mock_chat:
            data = answer_commission_question(commission, "how are you?", request)
        mock_chat.assert_called_once()
        self.assertEqual(data.get("source"), "ai")
        self.assertIn("doing well", data["answer"].lower())

    @override_settings(COMMISSION_AI_API_KEY="test-key", COMMISSION_AI_ENABLED=True)
    def test_ask_earn_more_next_month_than_current(self):
        from .commission_explanation import answer_commission_question
        from django.contrib.auth.models import User

        UserProfile.objects.filter(email="exp@test.com").update(
            personal_target=Decimal("200000")
        )
        order = Order.objects.create(
            organization=self.org,
            order_id="EXP-ORD-4",
            order_date=self.start,
            employee_id="EXP001",
            sales_amount=Decimal("100000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        user = User.objects.create_user(
            username="exp4@test.com",
            email="exp@test.com",
            password="test",
        )
        request = type("Req", (), {"user": user})()
        ai_reply = (
            "In January 2025 you earned ₹5,000. To beat that in February, "
            "close about ₹105,000 more in sales at your 5% rate."
        )
        with patch(
            "commissions.commission_ai._call_chat_completion",
            return_value=ai_reply,
        ) as mock_chat:
            data = answer_commission_question(
                commission,
                "How can I earn more commission next month than current month commission?",
                request,
            )
        self.assertIn("february", data["answer"].lower())
        self.assertEqual(data.get("source"), "ai")
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[0]
        self.assertEqual(len(call_args), 3)
        _question, context, _runtime = call_args
        self.assertIn("current_period", context)
        self.assertIn("next_period_label", context)

    @override_settings(
        COMMISSION_AI_API_KEY="",
        COMMISSION_AI_ENABLED=True,
        COMMISSION_AI_PROVIDER="openai",
    )
    def test_ask_offline_when_ai_not_configured(self):
        from .commission_explanation import answer_commission_question
        from django.contrib.auth.models import User

        order = Order.objects.create(
            organization=self.org,
            order_id="EXP-ORD-5",
            order_date=self.start,
            employee_id="EXP001",
            sales_amount=Decimal("50000"),
            order_status="Success",
        )
        commission = calculate_commission_for_order(order)
        user = User.objects.create_user(
            username="exp5@test.com",
            email="exp@test.com",
            password="test",
        )
        request = type("Req", (), {"user": user})()
        data = answer_commission_question(commission, "How was this calculated?", request)
        self.assertEqual(data.get("source"), "offline")
        self.assertIn("OPENAI_API_KEY", data["answer"])
        self.assertIn("Ollama", data["answer"])


class UserSetupDuplicateTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.admin = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="testpass",
        )
        UserProfile.objects.create(
            organization=self.org,
            email="admin@test.com",
            name="Admin",
            role="Admin",
            employee_id="ADM001",
        )
        UserProfile.objects.create(
            organization=self.org,
            email="existing@test.com",
            name="Existing Rep",
            role="Sales Rep",
            employee_id="EMP100",
        )
        self.client = Client()
        token = Token.objects.create(user=self.admin)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def _payload(self, **overrides):
        base = {
            "email": "new@test.com",
            "name": "New Rep",
            "role": "Sales Rep",
            "employee_id": "EMP200",
        }
        base.update(overrides)
        return base

    def test_create_user_success(self):
        res = self.client.post(
            "/api/user-setup/",
            data=self._payload(),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(res.status_code, 201)

    def test_reject_duplicate_email(self):
        res = self.client.post(
            "/api/user-setup/",
            data=self._payload(email="existing@test.com", employee_id="EMP999"),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Email", res.json()["error"])

    def test_reject_duplicate_employee_id(self):
        res = self.client.post(
            "/api/user-setup/",
            data=self._payload(email="other@test.com", employee_id="EMP100"),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Employee ID", res.json()["error"])

    def _upload_csv(self, content):
        upload = SimpleUploadedFile(
            "users.csv",
            content.encode("utf-8"),
            content_type="text/csv",
        )
        return self.client.post(
            "/api/user-setup-upload/",
            data={"file": upload},
            **self.auth,
        )

    def test_csv_upload_creates_new_user(self):
        csv = (
            "email,role,employee_id,name\n"
            "csvnew@test.com,Sales Rep,EMP300,CSV New\n"
        )
        res = self._upload_csv(csv)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["success"], 1)
        self.assertEqual(res.json()["failed"], 0)
        self.assertTrue(
            UserProfile.objects.filter(email="csvnew@test.com").exists()
        )

    def test_csv_upload_rejects_duplicate_email(self):
        csv = (
            "email,role,employee_id,name\n"
            "existing@test.com,Sales Rep,EMP999,Duplicate Email\n"
        )
        res = self._upload_csv(csv)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["success"], 0)
        self.assertEqual(res.json()["failed"], 1)
        self.assertIn("Email", res.json()["errors"][0]["error"])

    def test_csv_upload_rejects_duplicate_employee_id(self):
        csv = (
            "email,role,employee_id,name\n"
            "csvother@test.com,Sales Rep,EMP100,Duplicate Emp ID\n"
        )
        res = self._upload_csv(csv)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["success"], 0)
        self.assertEqual(res.json()["failed"], 1)
        self.assertIn("Employee ID", res.json()["errors"][0]["error"])


class EmployeeDisputeTests(TestCase):
    def setUp(self):
        self.org = get_default_organization()
        self.start = date(2025, 3, 1)
        self.rep_profile = UserProfile.objects.create(
            organization=self.org,
            employee_id="REP001",
            email="rep@test.com",
            name="Sales Rep",
            role="Sales Rep",
        )
        self.admin_user = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="testpass",
        )
        UserProfile.objects.create(
            organization=self.org,
            email="admin@test.com",
            name="Admin",
            role="Admin",
            employee_id="ADM001",
        )
        self.rep_user = User.objects.create_user(
            username="rep@test.com",
            email="rep@test.com",
            password="testpass",
        )
        plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Rep Plan",
            effective_start_date=self.start,
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
        self.order = Order.objects.create(
            organization=self.org,
            order_id="ORD-DSP-2",
            order_date=self.start,
            employee_id="REP001",
            sales_amount=Decimal("5000"),
            order_status="Success",
        )
        calculate_commission_for_order(self.order)
        self.comm = Commission.objects.filter(sale__order=self.order).first()
        rep_token = Token.objects.create(user=self.rep_user)
        admin_token = Token.objects.create(user=self.admin_user)
        self.rep_auth = {"HTTP_AUTHORIZATION": f"Token {rep_token.key}"}
        self.admin_auth = {"HTTP_AUTHORIZATION": f"Token {admin_token.key}"}
        self.client = Client()

    def test_rep_can_submit_dispute_and_admin_sees_it(self):
        res = self.client.post(
            "/api/disputes/",
            {"commission": self.comm.id, "message": "Wrong commission amount"},
            content_type="application/json",
            **self.rep_auth,
        )
        self.assertEqual(res.status_code, 201)

        admin_list = self.client.get("/api/disputes/", **self.admin_auth)
        self.assertEqual(admin_list.status_code, 200)
        rows = admin_list.json()
        if isinstance(rows, dict):
            rows = rows.get("results", [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["message"], "Wrong commission amount")

    def test_dispute_acknowledge_then_delete(self):
        create = self.client.post(
            "/api/disputes/",
            {"commission": self.comm.id, "message": "Wrong amount"},
            content_type="application/json",
            **self.rep_auth,
        )
        dispute_id = create.json()["id"]

        resolve = self.client.post(
            f"/api/disputes/{dispute_id}/resolve/",
            {"status": "resolved", "resolution_message": "Recalculated correctly"},
            content_type="application/json",
            **self.admin_auth,
        )
        self.assertEqual(resolve.status_code, 200)

        del_before_ack = self.client.delete(
            f"/api/disputes/{dispute_id}/",
            **self.admin_auth,
        )
        self.assertEqual(del_before_ack.status_code, 400)

        ack = self.client.post(
            f"/api/disputes/{dispute_id}/acknowledge/",
            content_type="application/json",
            **self.rep_auth,
        )
        self.assertEqual(ack.status_code, 200)
        self.assertTrue(ack.json()["can_delete"])

        del_admin = self.client.delete(
            f"/api/disputes/{dispute_id}/",
            **self.admin_auth,
        )
        self.assertEqual(del_admin.status_code, 204)

        create2 = self.client.post(
            "/api/disputes/",
            {"commission": self.comm.id, "message": "Second dispute"},
            content_type="application/json",
            **self.rep_auth,
        )
        dispute_id2 = create2.json()["id"]
        self.client.post(
            f"/api/disputes/{dispute_id2}/resolve/",
            {"status": "rejected", "resolution_message": "No change needed"},
            content_type="application/json",
            **self.admin_auth,
        )
        self.client.post(
            f"/api/disputes/{dispute_id2}/acknowledge/",
            content_type="application/json",
            **self.rep_auth,
        )
        del_rep = self.client.delete(
            f"/api/disputes/{dispute_id2}/",
            **self.rep_auth,
        )
        self.assertEqual(del_rep.status_code, 204)


class SCLookupTableTests(TestCase):
    """SC Lookup table: tier rates by product, service, distribution + sales band."""

    def setUp(self):
        self.start = date(2025, 1, 1)
        self.org = get_default_organization()
        UserProfile.objects.create(
            organization=self.org,
            employee_id="REP001",
            email="rep@test.com",
            name="Sales Rep One",
            role="Sales Rep",
            position_name="Standard Rep Position",
        )
        self.lookup_plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Lookup Plan",
            effective_start_date=self.start,
            status="Active",
            role="Sales Rep",
            commission_table_type="LOOKUP",
        )
        SCLookupTable.objects.create(
            compensation_plan=self.lookup_plan,
            product_name="Widget Pro",
            service_name="",
            distribution="",
            from_amount=Decimal("0"),
            to_amount=Decimal("50000"),
            commission_rate=Decimal("5"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )
        SCLookupTable.objects.create(
            compensation_plan=self.lookup_plan,
            product_name="Widget Pro",
            service_name="Support",
            distribution="Partner",
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("12"),
            bonus_amount=Decimal("500"),
            is_active=True,
            sequence=2,
        )
        SCLookupTable.objects.create(
            compensation_plan=self.lookup_plan,
            product_name="",
            service_name="",
            distribution="",
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("3"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=99,
        )

    def _order(self, **kwargs):
        defaults = {
            "organization": self.org,
            "order_id": "O-LOOKUP",
            "order_date": self.start,
            "employee_id": "REP001",
            "position_name": "Standard Rep Position",
            "sales_amount": Decimal("10000"),
            "product_name": "Widget Pro",
            "service_name": "Support",
            "distribution": "Partner",
            "order_status": "Success",
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    def test_specific_row_wins_over_wildcard(self):
        order = self._order()
        tier = find_sc_lookup_tier(self.lookup_plan, order, order.sales_amount)
        self.assertIsNotNone(tier)
        self.assertEqual(tier.commission_rate, Decimal("12"))
        self.assertEqual(tier.distribution, "Partner")

    def test_wildcard_product_matches_any(self):
        order = self._order(
            order_id="O-WILD",
            product_name="Other Product",
            service_name="",
            distribution="",
            sales_amount=Decimal("20000"),
        )
        tier = find_sc_lookup_tier(self.lookup_plan, order, order.sales_amount)
        self.assertIsNotNone(tier)
        self.assertEqual(tier.commission_rate, Decimal("3"))

    def test_sales_band_excludes_row(self):
        order = self._order(
            order_id="O-HIGH",
            product_name="Widget Pro",
            service_name="",
            distribution="",
            sales_amount=Decimal("75000"),
        )
        tier = find_sc_lookup_tier(self.lookup_plan, order, order.sales_amount)
        self.assertIsNotNone(tier)
        self.assertEqual(tier.commission_rate, Decimal("3"))

    def test_commission_calculation_with_lookup(self):
        order = self._order(order_id="O-COMM")
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        # 10000 * 12% + 500 bonus = 1700
        self.assertEqual(commission.commission_amount, Decimal("1700.00"))


class OrderStatusCommissionTests(TestCase):
    """Commission is created only when order_status is Success."""

    def setUp(self):
        self.start = date(2025, 1, 1)
        self.org = get_default_organization()
        UserProfile.objects.create(
            organization=self.org,
            employee_id="REP001",
            email="rep@test.com",
            name="Sales Rep One",
            role="Sales Rep",
        )
        self.plan = CompensationPlan.objects.create(
            organization=self.org,
            plan_name="Status Plan",
            effective_start_date=self.start,
            status="Active",
            role="Sales Rep",
            commission_table_type="RATE",
        )
        SCRateTable.objects.create(
            compensation_plan=self.plan,
            from_amount=Decimal("0"),
            to_amount=None,
            commission_rate=Decimal("10"),
            bonus_amount=Decimal("0"),
            is_active=True,
            sequence=1,
        )

    def _order(self, order_id, status="Booked"):
        return Order.objects.create(
            organization=self.org,
            order_id=order_id,
            order_date=self.start,
            employee_id="REP001",
            sales_amount=Decimal("10000"),
            order_status=status,
        )

    def test_booked_order_skips_commission(self):
        order = self._order("O-BOOKED", status="Booked")
        self.assertIsNone(calculate_commission_for_order(order))
        self.assertEqual(Commission.objects.filter(sale__order=order).count(), 0)

    def test_success_order_generates_commission(self):
        order = self._order("O-SUCCESS", status="Success")
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("1000.00"))

    def test_booked_to_success_transition(self):
        order = self._order("O-TRANS", status="Booked")
        self.assertIsNone(calculate_commission_for_order(order))

        order.order_status = "Success"
        order.save(update_fields=["order_status"])
        commission = calculate_commission_for_order(order)
        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("1000.00"))

    def test_success_to_booked_clears_commission(self):
        order = self._order("O-REVERT", status="Success")
        self.assertIsNotNone(calculate_commission_for_order(order))

        order.order_status = "Booked"
        order.save(update_fields=["order_status"])
        self.assertIsNone(calculate_commission_for_order(order))
        self.assertEqual(Commission.objects.filter(sale__order=order).count(), 0)

    def test_admin_patch_order_status_via_api(self):
        from django.contrib.auth.models import User

        admin_user = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="test",
        )
        UserProfile.objects.create(
            organization=self.org,
            employee_id="ADM001",
            email="admin@test.com",
            name="Admin",
            role="Admin",
        )
        token = Token.objects.create(user=admin_user)
        client = Client()
        order = self._order("O-API", status="Booked")

        patch = client.patch(
            f"/api/orders/{order.id}/",
            {"order_status": "Success"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(patch.status_code, 200)
        body = patch.json()
        self.assertEqual(body["order_status"], "Success")
        self.assertTrue(body["has_commission"])
        self.assertEqual(float(body["commission_amount"]), 1000.0)
