from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .health import health_check, readiness_check
from .views import (
    EmployeeViewSet,
    CommissionViewSet,
    UserProfileListCreateView,
    UserProfileUploadView,
    CompensationPlanListCreateView,
    CompensationTierListCreateView,
    OrderListCreateView,
    HierarchyRelationshipListCreateView,
    signup,
    login,
    email_login,
    change_password,
    get_user_profile,
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

urlpatterns = [
    path("health/", health_check, name="health"),
    path("health/ready/", readiness_check, name="health-ready"),
    path("audit-logs/", audit_log_list, name="audit-logs"),
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
    path("", include(router.urls)),
    path("signup/", signup),
    path("login/", login),
    path("email-login/", email_login, name="email-login"),
    path("change-password/", change_password, name="change-password"),
    path("user-profile/", get_user_profile, name="user-profile"),
    path(
        "compensation-plans/",
        CompensationPlanListCreateView.as_view(),
        name="compensation-plans",
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
