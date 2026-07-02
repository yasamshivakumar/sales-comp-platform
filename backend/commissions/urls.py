from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .health import health_check, readiness_check
from . import enterprise_views
from . import integration_views
from . import ai_views
from .rule_views import (
    CommissionRuleListCreateView,
    CommissionRuleDetailView,
    commission_rule_choices,
)
from .explanation_views import (
    commission_explanation_view,
    commission_explanation_ask_view,
    commission_what_if_view,
)
from .views import (
    EmployeeViewSet,
    CommissionViewSet,
    UserProfileListCreateView,
    UserProfileUploadView,
    CompensationPlanListCreateView,
    CompensationPlanDetailView,
    CompensationTierListCreateView,
    OrderListCreateView,
    HierarchyRelationshipListCreateView,
    signup,
    invite_detail,
    invite_accept,
    book_demo_request,
    email_login,
    change_password,
    get_user_profile,
    employee_directory,
    commission_summary_report,
    sales_performance_report,
    employee_earnings_report,
    period_analytics_report,
    approve_commissions_view,
    commission_payroll_export,
    recalculate_commissions_view,
    audit_log_list,
    import_job_detail,
)

router = DefaultRouter()
router.register("employees", EmployeeViewSet)
router.register("commissions", CommissionViewSet, basename="commission")
router.register("territories", enterprise_views.TerritoryViewSet, basename="territory")
router.register("payout-runs", enterprise_views.PayoutRunViewSet, basename="payout-run")
router.register("disputes", enterprise_views.CommissionDisputeViewSet, basename="dispute")
router.register(
    "integrations",
    integration_views.ExternalIntegrationViewSet,
    basename="integration",
)

urlpatterns = [
    path("health/", health_check, name="health"),
    path("health/ready/", readiness_check, name="health-ready"),
    path(
        "integrations/providers/",
        integration_views.integration_providers,
        name="integration-providers",
    ),
    path(
        "integrations/<int:integration_id>/test/",
        integration_views.test_integration_connection,
        name="integration-test",
    ),
    path(
        "integrations/<int:integration_id>/sync/users/",
        integration_views.sync_integration_users,
        name="integration-sync-users",
    ),
    path(
        "integrations/<int:integration_id>/sync/orders/",
        integration_views.sync_integration_orders,
        name="integration-sync-orders",
    ),
    path(
        "integrations/<int:integration_id>/sync/full/",
        integration_views.sync_integration_full,
        name="integration-sync-full",
    ),
    path(
        "integrations/<int:integration_id>/sync-logs/",
        integration_views.integration_sync_logs,
        name="integration-sync-logs",
    ),
    path(
        "integrations/<int:integration_id>/synced-users/",
        integration_views.integration_synced_users,
        name="integration-synced-users",
    ),
    path(
        "integrations/webhook/<str:webhook_secret>/users/",
        integration_views.integration_webhook_users,
        name="integration-webhook-users",
    ),
    path(
        "integrations/webhook/<str:webhook_secret>/orders/",
        integration_views.integration_webhook_orders,
        name="integration-webhook-orders",
    ),
    path(
        "integrations/hubspot/webhook/<str:webhook_secret>/",
        integration_views.integration_hubspot_webhook,
        name="integration-hubspot-webhook",
    ),
    path(
        "integrations/<int:integration_id>/auto-sync/",
        integration_views.trigger_auto_sync,
        name="integration-auto-sync",
    ),
    path("audit-logs/", audit_log_list, name="audit-logs"),
    path("ai/status/", ai_views.ai_status, name="ai-status"),
    path(
        "ai/compensation-plan-builder/",
        ai_views.ai_compensation_plan_builder,
        name="ai-compensation-plan-builder",
    ),
    path(
        "ai/dashboard-insights/",
        ai_views.ai_dashboard_insights,
        name="ai-dashboard-insights",
    ),
    path("statements/me/", enterprise_views.employee_statement, name="statement-me"),
    path(
        "statements/export/",
        enterprise_views.employee_statement_export,
        name="statement-export",
    ),
    path("leaderboard/", enterprise_views.leaderboard, name="leaderboard"),
    path(
        "reports/advanced-analytics/",
        enterprise_views.advanced_analytics_report,
        name="advanced-analytics-report",
    ),
    path(
        "commissions/approve/manager/",
        enterprise_views.approve_manager_commissions_view,
        name="commission-approve-manager",
    ),
    path(
        "commissions/approve/finance/",
        enterprise_views.approve_finance_commissions_view,
        name="commission-approve-finance",
    ),
    path(
        "payout-runs/<int:run_id>/mark-paid/",
        enterprise_views.mark_payout_run_paid_view,
        name="payout-run-mark-paid",
    ),
    path(
        "disputes/<int:dispute_id>/resolve/",
        enterprise_views.resolve_commission_dispute,
        name="dispute-resolve",
    ),
    path(
        "disputes/<int:dispute_id>/acknowledge/",
        enterprise_views.acknowledge_commission_dispute,
        name="dispute-acknowledge",
    ),
    path("import-jobs/<int:job_id>/", import_job_detail, name="import-job-detail"),
    path(
        "commissions/approve/",
        approve_commissions_view,
        name="commission-approve",
    ),
    path(
        "commissions/export/",
        commission_payroll_export,
        name="commission-payroll-export",
    ),
    path(
        "commissions/recalculate/",
        recalculate_commissions_view,
        name="commission-recalculate",
    ),
    path(
        "commissions/what-if/",
        commission_what_if_view,
        name="commission-what-if",
    ),
    path(
        "commissions/<int:commission_id>/explanation/",
        commission_explanation_view,
        name="commission-explanation",
    ),
    path(
        "commissions/<int:commission_id>/explanation/ask/",
        commission_explanation_ask_view,
        name="commission-explanation-ask",
    ),
    path("employees/directory/", employee_directory, name="employee-directory"),
    path("", include(router.urls)),
    path("auth/signup/", signup, name="auth-signup"),
    path("marketing/book-demo/", book_demo_request, name="marketing-book-demo"),
    path("auth/invite/<str:token>/", invite_detail, name="auth-invite-detail"),
    path("auth/invite/<str:token>/accept/", invite_accept, name="auth-invite-accept"),
    path("auth/email-login/", email_login, name="auth-email-login"),
    path("auth/change-password/", change_password, name="auth-change-password"),
    path("user-profile/", get_user_profile, name="user-profile"),
    path(
        "compensation-plans/",
        CompensationPlanListCreateView.as_view(),
        name="compensation-plans",
    ),
    path(
        "compensation-plans/<int:pk>/",
        CompensationPlanDetailView.as_view(),
        name="compensation-plan-detail",
    ),
    path(
        "commission-rules/",
        CommissionRuleListCreateView.as_view(),
        name="commission-rules",
    ),
    path(
        "commission-rules/choices/",
        commission_rule_choices,
        name="commission-rule-choices",
    ),
    path(
        "commission-rules/<int:pk>/",
        CommissionRuleDetailView.as_view(),
        name="commission-rule-detail",
    ),
    path("user-setup/", UserProfileListCreateView.as_view(), name="user-setup"),
    path(
        "user-setup-upload/",
        UserProfileUploadView.as_view(),
        name="user-setup-upload",
    ),
    path(
        "hierarchy-relationships/",
        HierarchyRelationshipListCreateView.as_view(),
        name="hierarchy-relationships",
    ),
    path("compensation-tiers/", CompensationTierListCreateView.as_view()),
    path("orders/", OrderListCreateView.as_view(), name="orders"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("orders-upload/", views.OrderUploadView.as_view(), name="orders-upload"),
    path(
        "reports/commission-summary/",
        commission_summary_report,
        name="commission-summary-report",
    ),
    path(
        "reports/sales-performance/",
        sales_performance_report,
        name="sales-performance-report",
    ),
    path(
        "reports/employee-earnings/",
        employee_earnings_report,
        name="employee-earnings-report",
    ),
    path(
        "reports/period-analytics/",
        period_analytics_report,
        name="period-analytics-report",
    ),
]
