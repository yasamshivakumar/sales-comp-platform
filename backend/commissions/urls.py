from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .health import health_check, readiness_check
from . import enterprise_views
from . import integration_views
from . import ai_views
from .oidc_views import oidc_token_exchange
from . import auth_views
from .rule_views import (
    CommissionRuleListCreateView,
    CommissionRuleDetailView,
    commission_rule_choices,
)
from .plan_version_views import (
    PlanVersionListView,
    PlanVersionDetailView,
    clone_plan_version,
    publish_plan_version,
    archive_plan_version,
    compare_plan_versions,
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
    UserProfileUploadValidateView,
    UserProfileImportHistoryView,
    CompensationPlanListCreateView,
    CompensationPlanDetailView,
    compensation_plans_summary,
    compensation_plan_participants,
    compensation_plan_activity,
    compensation_plan_insights,
    compensation_plans_search,
    CompensationTierListCreateView,
    OrderListCreateView,
    HierarchyRelationshipListCreateView,
    signup,
    invite_detail,
    invite_accept,
    book_demo_request,
    email_login,
    change_password,
    session_status,
    logout,
    get_user_profile,
    employee_directory,
    employee_user_detail,
    commission_summary_report,
    sales_performance_report,
    sales_by_region_report,
    employee_earnings_report,
    period_analytics_report,
    command_center_report,
    employee_transparency_report,
    approve_commissions_view,
    commission_payroll_export,
    recalculate_commissions_view,
    audit_log_list,
    import_job_detail,
    commission_operations_summary,
    commission_operations_grid,
    commission_operations_detail,
    commission_operations_bulk,
    commission_adjustment_create,
    commission_operations_export,
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
        "integrations/center/catalog/",
        integration_views.integration_center_catalog,
        name="integration-center-catalog",
    ),
    path(
        "integrations/center/summary/",
        integration_views.integration_center_summary,
        name="integration-center-summary",
    ),
    path(
        "integrations/center/wizard/",
        integration_views.integration_center_wizard,
        name="integration-center-wizard",
    ),
    path(
        "integrations/center/activity/",
        integration_views.integration_center_activity,
        name="integration-center-activity",
    ),
    path(
        "integrations/center/identities/",
        integration_views.integration_center_identities,
        name="integration-center-identities",
    ),
    path(
        "integrations/center/<int:connection_id>/mappings/",
        integration_views.integration_center_mappings,
        name="integration-center-mappings",
    ),
    path(
        "integrations/center/<int:connection_id>/preview/",
        integration_views.integration_center_preview,
        name="integration-center-preview",
    ),
    path(
        "integrations/center/<int:connection_id>/sync/",
        integration_views.integration_center_sync,
        name="integration-center-sync",
    ),
    path(
        "integrations/center/<int:connection_id>/disconnect/",
        integration_views.integration_center_disconnect,
        name="integration-center-disconnect",
    ),
    path(
        "integrations/center/jobs/<int:job_id>/retry/",
        integration_views.integration_center_retry_job,
        name="integration-center-retry-job",
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
        "commissions/operations-summary/",
        commission_operations_summary,
        name="commission-operations-summary",
    ),
    path(
        "commissions/operations-grid/",
        commission_operations_grid,
        name="commission-operations-grid",
    ),
    path(
        "commissions/operations-detail/",
        commission_operations_detail,
        name="commission-operations-detail",
    ),
    path(
        "commissions/operations-bulk/",
        commission_operations_bulk,
        name="commission-operations-bulk",
    ),
    path(
        "commissions/adjustments/",
        commission_adjustment_create,
        name="commission-adjustment-create",
    ),
    path(
        "commissions/operations-export/",
        commission_operations_export,
        name="commission-operations-export",
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
    path("users/<int:pk>/", employee_user_detail, name="employee-user-detail"),
    path("", include(router.urls)),
    path("auth/signup/", signup, name="auth-signup"),
    path("marketing/book-demo/", book_demo_request, name="marketing-book-demo"),
    path("auth/invite/<str:token>/", invite_detail, name="auth-invite-detail"),
    path("auth/invite/<str:token>/accept/", invite_accept, name="auth-invite-accept"),
    path("auth/email-login/", email_login, name="auth-email-login"),
    path("auth/oidc-exchange/", oidc_token_exchange, name="auth-oidc-exchange"),
    path("auth/change-password/", change_password, name="auth-change-password"),
    path("auth/session/", session_status, name="auth-session"),
    path("auth/logout/", logout, name="auth-logout"),
    path("auth/mfa/verify/", auth_views.mfa_verify, name="auth-mfa-verify"),
    path("auth/mfa/status/", auth_views.mfa_status, name="auth-mfa-status"),
    path("auth/mfa/enroll/", auth_views.mfa_enroll_start, name="auth-mfa-enroll"),
    path(
        "auth/mfa/enroll/confirm/",
        auth_views.mfa_enroll_confirm,
        name="auth-mfa-enroll-confirm",
    ),
    path("auth/mfa/disable/", auth_views.mfa_disable, name="auth-mfa-disable"),
    path("auth/login-history/", auth_views.login_history, name="auth-login-history"),
    path("auth/sessions/", auth_views.auth_sessions_list, name="auth-sessions"),
    path(
        "auth/sessions/revoke-all/",
        auth_views.auth_sessions_revoke_all,
        name="auth-sessions-revoke-all",
    ),
    path(
        "auth/trusted-devices/",
        auth_views.trusted_devices_list,
        name="auth-trusted-devices",
    ),
    path(
        "auth/trusted-devices/<int:device_pk>/revoke/",
        auth_views.trusted_device_revoke,
        name="auth-trusted-device-revoke",
    ),
    path("user-profile/", get_user_profile, name="user-profile"),
    path(
        "compensation-plans/",
        CompensationPlanListCreateView.as_view(),
        name="compensation-plans",
    ),
    path(
        "compensation-plans/summary/",
        compensation_plans_summary,
        name="compensation-plans-summary",
    ),
    path(
        "compensation-plans/search/",
        compensation_plans_search,
        name="compensation-plans-search",
    ),
    path(
        "compensation-plans/<int:pk>/",
        CompensationPlanDetailView.as_view(),
        name="compensation-plan-detail",
    ),
    path(
        "compensation-plans/<int:pk>/participants/",
        compensation_plan_participants,
        name="compensation-plan-participants",
    ),
    path(
        "compensation-plans/<int:pk>/activity/",
        compensation_plan_activity,
        name="compensation-plan-activity",
    ),
    path(
        "compensation-plans/<int:pk>/insights/",
        compensation_plan_insights,
        name="compensation-plan-insights",
    ),
    path(
        "compensation-plans/<int:plan_id>/versions/",
        PlanVersionListView.as_view(),
        name="plan-versions",
    ),
    path(
        "compensation-plans/<int:plan_id>/versions/compare/",
        compare_plan_versions,
        name="plan-versions-compare",
    ),
    path(
        "compensation-plans/<int:plan_id>/versions/<int:version_id>/",
        PlanVersionDetailView.as_view(),
        name="plan-version-detail",
    ),
    path(
        "compensation-plans/<int:plan_id>/versions/<int:version_id>/clone/",
        clone_plan_version,
        name="plan-version-clone",
    ),
    path(
        "compensation-plans/<int:plan_id>/versions/<int:version_id>/publish/",
        publish_plan_version,
        name="plan-version-publish",
    ),
    path(
        "compensation-plans/<int:plan_id>/versions/<int:version_id>/archive/",
        archive_plan_version,
        name="plan-version-archive",
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
    path("user-setup/summary/", views.PeopleSummaryView.as_view(), name="people-summary"),
    path("user-setup/bulk/", views.PeopleBulkActionView.as_view(), name="people-bulk"),
    path("user-setup/<int:pk>/", views.PeopleDetailView.as_view(), name="people-detail"),
    path(
        "user-setup/<int:pk>/invite/",
        views.PeopleInviteActionView.as_view(),
        name="people-invite-action",
    ),
    path(
        "user-setup-upload/",
        UserProfileUploadView.as_view(),
        name="user-setup-upload",
    ),
    path(
        "user-setup-upload/validate/",
        UserProfileUploadValidateView.as_view(),
        name="user-setup-upload-validate",
    ),
    path(
        "user-setup-upload/history/",
        UserProfileImportHistoryView.as_view(),
        name="user-setup-upload-history",
    ),
    path(
        "hierarchy-relationships/",
        HierarchyRelationshipListCreateView.as_view(),
        name="hierarchy-relationships",
    ),
    path("compensation-tiers/", CompensationTierListCreateView.as_view()),
    path("orders/", OrderListCreateView.as_view(), name="orders"),
    path("orders/summary/", views.OrderSummaryView.as_view(), name="orders-summary"),
    path("orders/bulk/", views.OrderBulkActionView.as_view(), name="orders-bulk"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("orders-upload/", views.OrderUploadView.as_view(), name="orders-upload"),
    path(
        "orders-upload/validate/",
        views.OrderUploadValidateView.as_view(),
        name="orders-upload-validate",
    ),
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
        "reports/sales-by-region/",
        sales_by_region_report,
        name="sales-by-region-report",
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
    path(
        "reports/command-center/",
        command_center_report,
        name="command-center-report",
    ),
    path(
        "reports/employee-transparency/",
        employee_transparency_report,
        name="employee-transparency-report",
    ),
]
