from datetime import date

from django.db import models
from django.conf import settings
from django.utils import timezone


class Organization(models.Model):
    """Tenant boundary for multi-company deployments."""

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Phase 1.3 — org-level security policy (defaults preserve current behavior)
    require_mfa = models.BooleanField(
        default=False,
        help_text="Require MFA after password login for all users in this org.",
    )
    password_history_count = models.PositiveSmallIntegerField(
        default=5,
        help_text="Reject new passwords that match one of the last N passwords (0=off).",
    )
    password_max_age_days = models.PositiveIntegerField(
        default=0,
        help_text="Force password change after N days (0=disabled).",
    )
    session_idle_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Override TOKEN_TTL_MINUTES for this org (0=use global setting).",
    )
    max_concurrent_sessions = models.PositiveSmallIntegerField(
        default=1,
        help_text="Active API sessions allowed per user (platform enforces 1 DRF token).",
    )
    remember_device_days = models.PositiveIntegerField(
        default=30,
        help_text="Days a trusted device may skip MFA.",
    )
    alert_on_new_login_ip = models.BooleanField(
        default=True,
        help_text="Flag and audit logins from previously unseen IP addresses.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="employees",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=100)

    email = models.EmailField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="uniq_employee_email_per_org",
            ),
        ]

    def __str__(self):
        return self.name


class Sale(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="sales",
        null=True,
        blank=True,
    )

    order = models.OneToOneField(
        "Order",
        on_delete=models.CASCADE,
        related_name="sale_record",
        null=True,
        blank=True,
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_index=True
    )

    employee_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.employee.name} - {self.amount}"


class Territory(models.Model):
    """Sales territory for rep assignment and plan/order scoping."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="territories",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=64, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("organization", "code")

    def __str__(self):
        return f"{self.name} ({self.code})"


class Commission(models.Model):
    SCOPE_ORDER = "order"
    SCOPE_EMPLOYEE_MONTH = "employee_month"
    SCOPE_CHOICES = [
        (SCOPE_ORDER, "Order"),
        (SCOPE_EMPLOYEE_MONTH, "Employee month"),
    ]
    STATUS_CALCULATED = "calculated"
    STATUS_MANAGER_APPROVED = "manager_approved"
    STATUS_APPROVED = "approved"
    STATUS_PAID = "paid"
    STATUS_REJECTED = "rejected"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_CALCULATED, "Calculated"),
        (STATUS_MANAGER_APPROVED, "Manager approved"),
        (STATUS_APPROVED, "Finance approved"),
        (STATUS_PAID, "Paid"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_FAILED, "Failed"),
    ]
    LOCKED_STATUSES = (
        STATUS_MANAGER_APPROVED,
        STATUS_APPROVED,
        STATUS_PAID,
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_index=True
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="commissions",
        null=True,
        blank=True,
        db_index=True,
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        db_index=True
    )

    commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    compensation_plan = models.ForeignKey(
        "CompensationPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions",
    )

    plan_version = models.ForeignKey(
        "CommissionPlanVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commissions",
        help_text="Immutable plan version used for this calculation.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CALCULATED,
        db_index=True,
    )

    calculated_at = models.DateTimeField(auto_now_add=True, null=True)
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    manager_approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manager_approved_commissions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_approved_commissions",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payout_run = models.ForeignKey(
        "PayoutRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions",
    )

    commission_rule = models.ForeignKey(
        "CommissionRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions",
    )
    credit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    result_classification = models.CharField(max_length=50, blank=True, default="")
    earning_group = models.CharField(max_length=50, blank=True, default="")
    hold_until = models.DateField(null=True, blank=True)
    reason_code = models.CharField(max_length=100, blank=True, default="")
    rule_result_name = models.CharField(max_length=200, blank=True, default="")
    calculation_scope = models.CharField(
        max_length=32,
        choices=SCOPE_CHOICES,
        default=SCOPE_ORDER,
        db_index=True,
    )
    period_start = models.DateField(null=True, blank=True, db_index=True)
    period_end = models.DateField(null=True, blank=True, db_index=True)
    source_order_count = models.PositiveIntegerField(default=1)
    source_sales_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=10, blank=True, default="")
    reviewer = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions_to_review",
    )
    rejection_reason = models.TextField(blank=True, default="")
    supporting_document = models.ForeignKey(
        "CompensationDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_references",
        help_text="Policy / plan document referenced for this calculation.",
    )
    supporting_document_version = models.ForeignKey(
        "CompensationDocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_references",
    )
    override_used = models.BooleanField(default=False, db_index=True)
    applied_override = models.ForeignKey(
        "EmployeeCompensationOverride",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions",
        help_text="Employee override that superseded the plan rules, if any.",
    )
    calculation_trace = models.JSONField(
        default=dict,
        blank=True,
        help_text="Resolved plan / version / rule / override chain for this payout.",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "status", "calculated_at"],
                name="commission_org_status_calc_idx",
            ),
            models.Index(fields=["status", "calculated_at"]),
            models.Index(
                fields=[
                    "organization",
                    "calculation_scope",
                    "period_start",
                    "employee",
                ],
                name="comm_org_scope_period_idx",
            ),
            models.Index(
                fields=["plan_version", "period_start"],
                name="comm_plan_version_period_idx",
            ),
        ]

    def __str__(self):
        return f"{self.employee.name} - {self.commission_amount}"


class CommissionAdjustment(models.Model):
    """Manual money adjustment layered on engine-calculated commission_amount."""

    TYPE_MANUAL = "manual"
    TYPE_BONUS = "bonus"
    TYPE_CORRECTION = "correction"
    TYPE_CLAWBACK = "clawback"
    TYPE_CHOICES = [
        (TYPE_MANUAL, "Manual Adjustment"),
        (TYPE_BONUS, "Bonus"),
        (TYPE_CORRECTION, "Correction"),
        (TYPE_CLAWBACK, "Clawback"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="commission_adjustments",
        null=True,
        blank=True,
        db_index=True,
    )
    commission = models.ForeignKey(
        Commission,
        on_delete=models.CASCADE,
        related_name="adjustments",
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_MANUAL,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_adjustments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.adjustment_type} {self.amount} on commission #{self.commission_id}"


class CompensationPlan(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    PAY_PERIOD_CHOICES = [
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Annual', 'Annual'),
    ]

    PLAN_BASIS_CHOICES = [
        ('Product', 'Product'),
        ('Service', 'Service'),
        ('Individual', 'Individual'),
        ('Role', 'Role'),
        ('Region', 'Region'),
        ('Customer Segment', 'Customer Segment'),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="compensation_plans",
        null=True,
        blank=True,
    )

    # Basic Information
    plan_name = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    effective_start_date = models.DateField()
    effective_end_date = models.DateField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Draft'
    )

    pay_period_type = models.CharField(
        max_length=20,
        choices=PAY_PERIOD_CHOICES,
        default='Monthly'
    )

    plan_basis = models.CharField(
        max_length=50,
        choices=PLAN_BASIS_CHOICES,
        default='Individual'
    )

    # ADD THIS SECTION
    COMMISSION_TABLE_TYPE_CHOICES = [
        ('RATE', 'SC Rate Table'),
        ('HIGHEST', 'Highest Rate Table'),
        ('MARGINAL', 'Marginal Rate Table'),
        ('FLAT', 'SC Flat Rate Table'),
        ('LOOKUP', 'SC Lookup Table'),
    ]

    TIER_CALCULATION_FLAT = 'flat'
    TIER_CALCULATION_MARGINAL = 'marginal'
    TIER_CALCULATION_CHOICES = [
        (TIER_CALCULATION_FLAT, 'Flat (whole amount at the landing tier rate)'),
        (TIER_CALCULATION_MARGINAL, 'Marginal (each slice at its own tier rate)'),
    ]

    commission_table_type = models.CharField(
        max_length=10,
        choices=COMMISSION_TABLE_TYPE_CHOICES,
        default='RATE',
        help_text='Select which commission table type this plan uses.'
    )

    tier_calculation_method = models.CharField(
        max_length=10,
        choices=TIER_CALCULATION_CHOICES,
        default=TIER_CALCULATION_FLAT,
        help_text=(
            'Flat applies the landing tier rate to the whole amount. '
            'Marginal applies each tier rate only to the portion of sales '
            'that falls within that tier (like tax brackets).'
        ),
    )

    # Assignment Criteria
    position_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text='Unique position name used during commission calculations'
    )

    role = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    territory = models.ForeignKey(
        Territory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compensation_plans",
    )

    title = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    business_group = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    PLAN_TYPE_SALES = "sales_commission"
    PLAN_TYPE_BONUS = "bonus_plan"
    PLAN_TYPE_OVERRIDE = "manager_override"
    PLAN_TYPE_CHANNEL = "channel_incentive"
    PLAN_TYPE_SPIFF = "spiff"
    PLAN_TYPE_CHOICES = [
        (PLAN_TYPE_SALES, "Sales Commission"),
        (PLAN_TYPE_BONUS, "Bonus Plan"),
        (PLAN_TYPE_OVERRIDE, "Manager Override"),
        (PLAN_TYPE_CHANNEL, "Channel Incentive"),
        (PLAN_TYPE_SPIFF, "SPIFF"),
    ]
    plan_type = models.CharField(
        max_length=32,
        choices=PLAN_TYPE_CHOICES,
        default=PLAN_TYPE_SALES,
        db_index=True,
        help_text="Business classification for catalog filtering and reporting.",
    )
    owner = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Owning team or function (e.g. Sales Operations).",
    )
    approver = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Approving role or person (e.g. Finance Director).",
    )
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_compensation_plans",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "plan_name"],
                name="uniq_plan_name_per_org",
            ),
        ]

    def __str__(self):
        return self.plan_name


# =====================================================
# Commission Plan Version
# Immutable, effective-dated snapshot of a compensation plan.
# Draft -> editable; Published -> immutable; Archived -> read-only history.
# The calculation engine always resolves the Published version whose
# effective range contains the order date.
# =====================================================
class CommissionPlanVersion(models.Model):
    STATUS_DRAFT = "Draft"
    STATUS_PUBLISHED = "Published"
    STATUS_ARCHIVED = "Archived"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="commission_plan_versions",
        null=True,
        blank=True,
        db_index=True,
    )
    compensation_plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True,
        blank=True,
        help_text="Leave blank for open-ended effectivity.",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_plan_versions",
    )
    created_from_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_versions",
    )
    description = models.TextField(blank=True, default="")

    # Snapshot of calculation/assignment config (copied from the plan and
    # frozen once the version is published).
    pay_period_type = models.CharField(
        max_length=20,
        choices=CompensationPlan.PAY_PERIOD_CHOICES,
        default="Monthly",
    )
    plan_basis = models.CharField(
        max_length=50,
        choices=CompensationPlan.PLAN_BASIS_CHOICES,
        default="Individual",
    )
    commission_table_type = models.CharField(
        max_length=10,
        choices=CompensationPlan.COMMISSION_TABLE_TYPE_CHOICES,
        default="RATE",
    )
    tier_calculation_method = models.CharField(
        max_length=10,
        choices=CompensationPlan.TIER_CALCULATION_CHOICES,
        default=CompensationPlan.TIER_CALCULATION_FLAT,
    )
    position_name = models.CharField(max_length=200, blank=True, null=True)
    role = models.CharField(max_length=100, blank=True, null=True)
    territory = models.ForeignKey(
        Territory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plan_versions",
    )
    title = models.CharField(max_length=100, blank=True, null=True)
    business_group = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["compensation_plan_id", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["compensation_plan", "version_number"],
                name="uniq_plan_version_number",
            ),
            models.UniqueConstraint(
                fields=["compensation_plan"],
                condition=models.Q(status="Draft"),
                name="uniq_one_draft_version_per_plan",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=models.F("effective_from"))
                ),
                name="plan_version_effective_range_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "status", "effective_from"],
                name="cpv_org_status_from_idx",
            ),
            models.Index(
                fields=["compensation_plan", "status", "effective_from"],
                name="cpv_plan_status_from_idx",
            ),
        ]

    @property
    def is_editable(self):
        return self.status == self.STATUS_DRAFT

    def __str__(self):
        return (
            f"{self.compensation_plan.plan_name} v{self.version_number} "
            f"({self.status})"
        )


class PlanVersionQuota(models.Model):
    """Monthly quota attached to a plan version (quota changes do not require
    a new plan or a new version)."""

    plan_version = models.ForeignKey(
        CommissionPlanVersion,
        on_delete=models.CASCADE,
        related_name="quotas",
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    quota_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year", "month"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan_version", "year", "month"],
                name="uniq_quota_per_version_month",
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1) & models.Q(month__lte=12),
                name="quota_month_valid",
            ),
        ]

    def __str__(self):
        return f"{self.plan_version} — {self.year}-{self.month:02d}: {self.quota_amount}"


# =====================================================
# SC Rate Table
# Tiered commission rates
# Example:
# 0 - 100000      => 5%
# 100001 - 500000 => 7%
# 500001+         => 10%
# =====================================================
class SCRateTable(models.Model):
    compensation_plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.CASCADE,
        related_name='sc_rate_tables'
    )

    plan_version = models.ForeignKey(
        CommissionPlanVersion,
        on_delete=models.CASCADE,
        related_name="sc_rate_tables",
        null=True,
        blank=True,
    )

    tier_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    from_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    to_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        help_text='Leave blank for no upper limit'
    )

    commission_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text='Percentage value. Example: 5.00 = 5%'
    )

    bonus_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    sequence = models.PositiveIntegerField(
        default=1
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['sequence', 'from_amount']

    def __str__(self):
        return (
            f"{self.compensation_plan.plan_name} - "
            f"{self.from_amount} to {self.to_amount or 'Above'}"
        )


# =====================================================
# SC Flat Rate Table
# Fixed commission regardless of tiers
# Example:
# All sales => 3%
# =====================================================
class SCFlatRateTable(models.Model):
    compensation_plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.CASCADE,
        related_name='sc_flat_rate_tables'
    )

    plan_version = models.ForeignKey(
        CommissionPlanVersion,
        on_delete=models.CASCADE,
        related_name="sc_flat_rate_tables",
        null=True,
        blank=True,
    )

    flat_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text='Percentage value. Example: 3.00 = 3%'
    )

    bonus_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    minimum_sales_threshold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.compensation_plan.plan_name} - "
            f"{self.flat_rate}%"
        )


# =====================================================
# SC Lookup Table
# Tier rates matched by product, service, distribution + sales band
# Blank dimension on a row = wildcard (matches any value on the order)
# =====================================================
class SCLookupTable(models.Model):
    compensation_plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.CASCADE,
        related_name="sc_lookup_tables",
    )

    plan_version = models.ForeignKey(
        CommissionPlanVersion,
        on_delete=models.CASCADE,
        related_name="sc_lookup_tables",
        null=True,
        blank=True,
    )

    tier_name = models.CharField(max_length=100, blank=True, default="")

    product_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Leave blank to match any product",
    )
    service_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Leave blank to match any service",
    )
    distribution = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Leave blank to match any distribution channel",
    )

    from_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    to_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Leave blank for no upper limit",
    )

    commission_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="Percentage value. Example: 5.00 = 5%",
    )

    bonus_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        parts = [p for p in (self.product_name, self.service_name, self.distribution) if p]
        label = " / ".join(parts) if parts else "Any"
        return f"{self.compensation_plan.plan_name} — {label} @ {self.commission_rate}%"


class CompensationTier(models.Model):
    plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.CASCADE,
        related_name='tiers'
    )

    tier_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    min_sales = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    max_sales = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    bonus_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['min_sales']

    def __str__(self):
        return (
            f"{self.plan.plan_name} - "
            f"{self.tier_name or 'Tier'}"
        )

class UserProfile(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="user_profiles",
        null=True,
        blank=True,
    )

    # User Section
    enable_login = models.BooleanField(default=False)
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=100, default='Sales Rep', db_index=True)

    # People Section
    username = models.CharField(max_length=150, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    prefix = models.CharField(max_length=50, blank=True)
    employee_id = models.CharField(max_length=100, blank=True, db_index=True)
    crm_user_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="External CRM owner/user ID (e.g. HubSpot owner id).",
    )
    crm_alt_user_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Secondary CRM user id (e.g. HubSpot userId vs owner id on deals).",
    )

    personal_target = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    personal_currency = models.CharField(
        max_length=10,
        default='INR'
    )
    business_group = models.CharField(
        max_length=100,
        blank=True
    )
    territory = models.ForeignKey(
        Territory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
    )

    # Title Section
    title = models.CharField(max_length=255, blank=True)
    pay_period_type = models.CharField(
        max_length=50,
        default='Monthly'
    )

    # Position Section
    position_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    position_title = models.CharField(
        max_length=255,
        blank=True
    )

    # Legacy / Optional Fields
    hire_date = models.DateField(
        null=True,
        blank=True
    )
    unique_name = models.CharField(
        max_length=255,
        blank=True
    )
    hierarchy = models.CharField(
        max_length=255,
        blank=True
    )
    description = models.TextField(blank=True)
    function_name = models.CharField(
        max_length=255,
        blank=True
    )
    title_category = models.CharField(
        max_length=255,
        blank=True
    )
    level = models.CharField(
        max_length=255,
        blank=True
    )
    market = models.CharField(
        max_length=255,
        blank=True
    )
    phone = models.CharField(max_length=40, blank=True, default="")
    department = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Department / org unit (People & Access).",
    )
    account_status = models.CharField(
        max_length=32,
        blank=True,
        default="",
        db_index=True,
        help_text="Optional override: active, suspended, deactivated.",
    )
    commission_eligible = models.BooleanField(
        default=True,
        help_text="Whether this person is eligible for commission calculations.",
    )
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last password change time (auth User).",
    )
    force_password_change = models.BooleanField(
        default=False,
        help_text="When true, API access is limited to change-password / logout.",
    )
    mfa_enabled = models.BooleanField(
        default=False,
        help_text="User has at least one confirmed MFA device.",
    )
    custom_permissions = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional permission code overrides for custom roles.",
    )
    # Self-service account preferences (timezone, language, notifications, etc.)
    account_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Personal prefs: timezone, language, notifications, ui.",
    )
    assigned_compensation_plan = models.ForeignKey(
        "CompensationPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_participants",
        help_text="Explicit compensation plan assignment for this participant.",
    )
    comp_effective_date = models.DateField(
        null=True,
        blank=True,
        help_text="Effective date for compensation plan / quota assignment.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="uniq_profile_email_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "crm_user_id"],
                condition=models.Q(crm_user_id__gt=""),
                name="uniq_crm_user_id_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class UserInvite(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="user_invites",
    )
    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="login_invites",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_user_invites",
    )
    email = models.EmailField(db_index=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "email", "accepted_at"],
                name="invite_org_email_accept_idx",
            ),
        ]

    def __str__(self):
        return f"Invite for {self.email}"


class HierarchyRelationship(models.Model):
    parent_participant = models.ForeignKey(
        'UserProfile',
        on_delete=models.CASCADE,
        related_name='child_relationships'
    )

    child_participant = models.ForeignKey(
        'UserProfile',
        on_delete=models.CASCADE,
        related_name='parent_relationships'
    )

    split_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.00
    )

    effective_start_date = models.DateField(auto_now_add=True)
    effective_end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('parent_participant', 'child_participant') 

    def __str__(self):
        return (
            f"{self.parent_participant.first_name} -> "
            f"{self.child_participant.first_name} "
            f"({self.split_percentage}%)"
        )

class Order(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True,
    )

    # Transaction identifiers
    order_id = models.CharField(max_length=100, db_index=True)
    order_date = models.DateField()

    # Participant references
    employee_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    position_name = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    # Business context
    service_name = models.CharField(max_length=200, blank=True, null=True)
    product_name = models.CharField(max_length=200, blank=True, null=True)
    distribution = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_index=True,
        help_text="Distribution channel (used by SC Lookup Table matching)",
    )
    region = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    customer_segment = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Customer / account name for the transaction.",
    )
    business_group = models.CharField(max_length=100, blank=True, null=True)
    territory = models.ForeignKey(
        Territory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    # Financial values
    sales_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        validators=[],  # Validators added below
    )
    # quantity = models.DecimalField(
    #     max_digits=12,
    #     decimal_places=2,
    #     default=1
    # )

    # Status fields
    order_status = models.CharField(
        max_length=50,
        default="Booked"
    )
    currency = models.CharField(
        max_length=10,
        default="INR"
    )

    # Transaction operations enrichment (additive; does not change Success eligibility)
    source = models.CharField(
        max_length=32,
        blank=True,
        default="manual",
        help_text="Origin: manual, csv, crm, imported.",
    )
    sales_credits = models.JSONField(
        default=list,
        blank=True,
        help_text="Credit split rows: [{employee_id, name, role, percent}].",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_created",
    )

    needs_recalculation = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Set when order data changes and commission should be recalculated.",
    )

    # CRM sync metadata
    crm_provider = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        db_index=True,
        help_text="CRM source for this order (hubspot, salesforce, zoho, etc.).",
    )
    crm_owner_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="CRM owner/user id at import time (audit trail).",
    )
    external_integration = models.ForeignKey(
        "ExternalIntegration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_orders",
        help_text="Integration that imported this order, when applicable.",
    )

    # Audit fields
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "order_id"],
                name="uniq_order_id_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.order_id} - {self.sales_amount}"


class ImportJob(models.Model):
    JOB_ORDERS = "orders"
    JOB_USERS = "users"
    JOB_TYPE_CHOICES = [
        (JOB_ORDERS, "Orders CSV"),
        (JOB_USERS, "Users CSV"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="import_jobs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_jobs",
    )
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    source_filename = models.CharField(max_length=255, blank=True)
    input_file = models.FileField(upload_to="imports/%Y/%m/")
    row_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.job_type} #{self.pk} ({self.status})"


class PayoutRun(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PAID = "paid"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PAID, "Paid"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="payout_runs",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    payment_reference = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payout_runs_created",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.status})"


class CommissionDispute(models.Model):
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    commission = models.ForeignKey(
        Commission,
        on_delete=models.CASCADE,
        related_name="disputes",
    )
    raised_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_disputes_raised",
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )
    resolution_message = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_disputes_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    employee_acknowledged_at = models.DateTimeField(null=True, blank=True)
    employee_acknowledged_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_disputes_acknowledged",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dispute #{self.pk} ({self.status})"


class AuditLogQuerySet(models.QuerySet):
    """Block bulk updates; allow queryset delete only for ORM cascades (tenant wipe)."""

    def update(self, **kwargs):
        raise ValueError("AuditLog rows are immutable and cannot be updated")


class AuditLogManager(models.Manager):
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)


class AuditLog(models.Model):
    """Immutable enterprise activity trail (Activity & Compliance Center)."""

    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_SUCCESS = "success"
    SEVERITY_CHOICES = (
        (SEVERITY_INFO, "Information"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
        (SEVERITY_SUCCESS, "Success"),
    )

    SOURCE_WEB = "web"
    SOURCE_API = "api"
    SOURCE_CSV = "csv_import"
    SOURCE_CRM = "crm_sync"
    SOURCE_JOB = "background_job"
    SOURCE_CHOICES = (
        (SOURCE_WEB, "Web"),
        (SOURCE_API, "API"),
        (SOURCE_CSV, "CSV Import"),
        (SOURCE_CRM, "CRM Sync"),
        (SOURCE_JOB, "Background Job"),
    )

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    user = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    user_email = models.EmailField(blank=True, db_index=True)
    employee_id = models.CharField(max_length=64, blank=True, db_index=True)
    role = models.CharField(max_length=64, blank=True, db_index=True)
    business_unit = models.CharField(max_length=128, blank=True, db_index=True)

    action = models.CharField(max_length=64, db_index=True)
    module = models.CharField(max_length=64, blank=True, db_index=True)
    entity_type = models.CharField(max_length=64, blank=True, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True, db_index=True)
    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_INFO,
        blank=True,
        db_index=True,
    )
    source = models.CharField(
        max_length=32,
        choices=SOURCE_CHOICES,
        default=SOURCE_WEB,
        blank=True,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_SUCCESS,
        blank=True,
        db_index=True,
    )

    plan_version = models.ForeignKey(
        "CommissionPlanVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    detail = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    device = models.CharField(max_length=128, blank=True)
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    request_id = models.CharField(max_length=36, blank=True, db_index=True)
    search_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditLogManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "-created_at"],
                name="audit_org_created_idx",
            ),
            models.Index(
                fields=["organization", "module", "-created_at"],
                name="audit_org_module_idx",
            ),
            models.Index(
                fields=["organization", "severity", "-created_at"],
                name="audit_org_severity_idx",
            ),
            models.Index(
                fields=["organization", "action"],
                name="audit_org_action_idx",
            ),
            models.Index(
                fields=["organization", "entity_type", "entity_id"],
                name="audit_org_entity_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("AuditLog rows are immutable and cannot be updated")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog rows are immutable and cannot be deleted")

    def __str__(self):
        return f"{self.action} ({self.user_email or 'system'})"


class ExternalIntegration(models.Model):
    """Third-party CRM / API connection for syncing users and orders."""

    PROVIDER_SALESFORCE = "salesforce"
    PROVIDER_GENERIC_REST = "generic_rest"
    PROVIDER_WEBHOOK = "webhook"
    PROVIDER_HUBSPOT = "hubspot"
    PROVIDER_ZOHO = "zoho"
    PROVIDER_DYNAMICS = "dynamics"
    PROVIDER_CHOICES = [
        (PROVIDER_SALESFORCE, "Salesforce"),
        (PROVIDER_GENERIC_REST, "Generic REST API"),
        (PROVIDER_WEBHOOK, "Webhook / Zapier"),
        (PROVIDER_HUBSPOT, "HubSpot (REST)"),
        (PROVIDER_ZOHO, "Zoho CRM"),
        (PROVIDER_DYNAMICS, "Microsoft Dynamics (coming soon)"),
    ]

    STATUS_CONNECTED = "connected"
    STATUS_SYNCING = "syncing"
    STATUS_FAILED = "failed"
    STATUS_AUTH_EXPIRED = "auth_expired"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_CHOICES = [
        (STATUS_CONNECTED, "Connected"),
        (STATUS_SYNCING, "Syncing"),
        (STATUS_FAILED, "Failed"),
        (STATUS_AUTH_EXPIRED, "Authentication expired"),
        (STATUS_DISCONNECTED, "Disconnected"),
    ]

    FREQ_REALTIME = "realtime"
    FREQ_HOURLY = "hourly"
    FREQ_DAILY = "daily"
    FREQ_MANUAL = "manual"
    FREQ_CHOICES = [
        (FREQ_REALTIME, "Real-time"),
        (FREQ_HOURLY, "Hourly"),
        (FREQ_DAILY, "Daily"),
        (FREQ_MANUAL, "Manual"),
    ]

    AUTH_OAUTH = "oauth"
    AUTH_TOKEN = "token"
    AUTH_PASSWORD = "password"
    AUTH_CHOICES = [
        (AUTH_OAUTH, "OAuth 2.0"),
        (AUTH_TOKEN, "Access token"),
        (AUTH_PASSWORD, "Username / password"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="external_integrations",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True)
    connection_status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_CONNECTED,
        db_index=True,
    )
    sync_frequency = models.CharField(
        max_length=20,
        choices=FREQ_CHOICES,
        default=FREQ_MANUAL,
    )
    auth_method = models.CharField(
        max_length=20,
        choices=AUTH_CHOICES,
        default=AUTH_TOKEN,
        blank=True,
    )
    connected_org_name = models.CharField(max_length=255, blank=True, default="")
    connected_user_email = models.EmailField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    objects_enabled = models.JSONField(
        default=dict,
        blank=True,
        help_text="e.g. {users: true, deals: true, accounts: false, products: false}",
    )
    sync_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Trigger and import rules for deals/orders.",
    )
    credentials = models.JSONField(default=dict, blank=True)
    encrypted_credentials = models.TextField(
        blank=True,
        default="",
        help_text="Fernet-sealed credential blob (preferred over plaintext JSON).",
    )
    config = models.JSONField(default=dict, blank=True)
    webhook_secret = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
    )
    last_user_sync_at = models.DateTimeField(null=True, blank=True)
    last_order_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    auto_sync_enabled = models.BooleanField(
        default=False,
        help_text="Periodically pull CRM users and deals into Incentra.",
    )
    auto_sync_interval_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Minimum minutes between automatic sync runs.",
    )
    last_auto_sync_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integrations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.provider})"

    def get_decrypted_credentials(self):
        from .secrets import get_secret_manager

        return get_secret_manager().decrypt_credentials(
            self.encrypted_credentials or None,
            legacy_credentials=self.credentials or {},
        )

    def set_encrypted_credentials(self, credentials: dict):
        from .credential_crypto import public_credential_metadata
        from .secrets import get_secret_manager

        manager = get_secret_manager()
        self.encrypted_credentials = manager.encrypt_credentials(credentials or {})
        # Never persist secret values in the JSON column (metadata only).
        self.credentials = public_credential_metadata(credentials or {})


class IntegrationSyncLog(models.Model):
    SYNC_USERS = "users"
    SYNC_ORDERS = "orders"
    SYNC_WEBHOOK_USERS = "webhook_users"
    SYNC_WEBHOOK_ORDERS = "webhook_orders"
    SYNC_HUBSPOT_WEBHOOK = "hubspot_webhook"
    SYNC_AUTO = "auto"
    SYNC_TYPE_CHOICES = [
        (SYNC_USERS, "Users pull"),
        (SYNC_ORDERS, "Orders pull"),
        (SYNC_WEBHOOK_USERS, "Users webhook"),
        (SYNC_WEBHOOK_ORDERS, "Orders webhook"),
        (SYNC_HUBSPOT_WEBHOOK, "HubSpot webhook"),
        (SYNC_AUTO, "Automatic scheduled sync"),
    ]

    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    integration = models.ForeignKey(
        ExternalIntegration,
        on_delete=models.CASCADE,
        related_name="sync_logs",
    )
    sync_type = models.CharField(max_length=32, choices=SYNC_TYPE_CHOICES, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
        db_index=True,
    )
    records_fetched = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_syncs",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.integration.name} {self.sync_type} ({self.status})"


class CRMFieldMapping(models.Model):
    """Visual field mapping row for a CRM connection (replaces raw JSON for admins)."""

    connection = models.ForeignKey(
        ExternalIntegration,
        on_delete=models.CASCADE,
        related_name="field_mappings",
    )
    source_object = models.CharField(max_length=64, db_index=True)
    source_field = models.CharField(max_length=128)
    target_field = models.CharField(max_length=128)
    is_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_object", "target_field"]
        unique_together = [("connection", "source_object", "target_field")]

    def __str__(self):
        return f"{self.source_object}.{self.source_field} → {self.target_field}"


class CRMSyncJob(models.Model):
    """Enterprise sync job record (complements IntegrationSyncLog)."""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_PARTIAL = "partial"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_PARTIAL, "Partial"),
    ]

    connection = models.ForeignKey(
        ExternalIntegration,
        on_delete=models.CASCADE,
        related_name="sync_jobs",
    )
    sync_type = models.CharField(max_length=32, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.PositiveIntegerField(default=0)
    failed_records = models.PositiveIntegerField(default=0)
    error_details = models.JSONField(default=list, blank=True)
    result = models.JSONField(default=dict, blank=True)
    sync_log = models.ForeignKey(
        IntegrationSyncLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_jobs",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_sync_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SyncJob #{self.pk} {self.sync_type} ({self.status})"


class CRMIdentityMapping(models.Model):
    """Maps CRM user IDs to Incentra employees."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="crm_identity_mappings",
        null=True,
        blank=True,
    )
    connection = models.ForeignKey(
        ExternalIntegration,
        on_delete=models.CASCADE,
        related_name="identity_mappings",
        null=True,
        blank=True,
    )
    crm_provider = models.CharField(max_length=32, db_index=True)
    crm_user_id = models.CharField(max_length=128, db_index=True)
    employee_id = models.CharField(max_length=64, db_index=True)
    employee_email = models.EmailField(blank=True, default="")
    profile = models.ForeignKey(
        "UserProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_identity_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["crm_provider", "crm_user_id"]
        unique_together = [("organization", "crm_provider", "crm_user_id")]

    def __str__(self):
        return f"{self.crm_provider}:{self.crm_user_id} → {self.employee_id}"


class CommissionRule(models.Model):
    """Xactly-style commission/credit rule attached to a compensation plan."""

    RULE_TYPE_COMMISSION_FLAT = "commission_flat"
    RULE_TYPE_COMMISSION_RATE = "commission_rate"
    RULE_TYPE_CREDIT_AMOUNT = "credit_amount"
    RULE_TYPE_CREDIT_PERCENT = "credit_percent"
    RULE_TYPE_MULTIPLIER = "multiplier"
    RULE_TYPE_CHOICES = [
        (RULE_TYPE_COMMISSION_FLAT, "Commission - Flat Rate"),
        (RULE_TYPE_COMMISSION_RATE, "Commission - Rate"),
        (RULE_TYPE_CREDIT_AMOUNT, "Credit - Amount"),
        (RULE_TYPE_CREDIT_PERCENT, "Credit - Percentage"),
        (RULE_TYPE_MULTIPLIER, "Multiplier"),
    ]

    # Evaluation hierarchy. Employee overrides live in their own model and
    # always outrank rules; these scopes order the plan-owned rules below them.
    SCOPE_TERRITORY = "territory"
    SCOPE_BUSINESS_UNIT = "business_unit"
    SCOPE_ROLE = "role"
    SCOPE_PLAN_DEFAULT = "plan_default"
    SCOPE_CHOICES = [
        (SCOPE_TERRITORY, "Territory Rule"),
        (SCOPE_BUSINESS_UNIT, "Business Unit Rule"),
        (SCOPE_ROLE, "Role Rule"),
        (SCOPE_PLAN_DEFAULT, "Compensation Plan Default"),
    ]
    # Priority 1 is reserved for employee overrides.
    DEFAULT_SCOPE_PRIORITY = {
        SCOPE_TERRITORY: 2,
        SCOPE_BUSINESS_UNIT: 3,
        SCOPE_ROLE: 4,
        SCOPE_PLAN_DEFAULT: 5,
    }

    LOGIC_AND = "and"
    LOGIC_OR = "or"
    LOGIC_CHOICES = [
        (LOGIC_AND, "Match all conditions (AND)"),
        (LOGIC_OR, "Match any condition (OR)"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="commission_rules",
        null=True,
        blank=True,
    )
    compensation_plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.CASCADE,
        related_name="commission_rules",
        null=True,
        blank=True,
    )
    plan_version = models.ForeignKey(
        "CommissionPlanVersion",
        on_delete=models.CASCADE,
        related_name="commission_rules",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    rule_type = models.CharField(
        max_length=32,
        choices=RULE_TYPE_CHOICES,
        default=RULE_TYPE_COMMISSION_RATE,
    )
    multiplier = models.DecimalField(max_digits=12, decimal_places=4, default=1)

    tags = models.JSONField(default=list, blank=True)
    version_label = models.CharField(
        max_length=255,
        blank=True,
        default="Start of Time - End of Time",
    )
    effective_start_date = models.DateField(null=True, blank=True)
    effective_end_date = models.DateField(null=True, blank=True)
    active_start_date = models.DateField(null=True, blank=True)
    active_end_date = models.DateField(null=True, blank=True)

    scope = models.CharField(
        max_length=32,
        choices=SCOPE_CHOICES,
        default=SCOPE_PLAN_DEFAULT,
        db_index=True,
        help_text="Hierarchy level this rule represents.",
    )
    priority = models.PositiveIntegerField(
        default=5,
        db_index=True,
        help_text="Lower runs first. 1 is reserved for employee overrides.",
    )
    condition_logic = models.CharField(
        max_length=8,
        choices=LOGIC_CHOICES,
        default=LOGIC_AND,
    )
    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    stop_on_match = models.BooleanField(default=False)
    apply_to_all_plan_participants = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "When true, this rule applies to every employee who belongs to the "
            "rule's compensation plan (current and future). Individual "
            "assignments are not required."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    assigned_employees = models.ManyToManyField(
        "UserProfile",
        through="EmployeeCommissionRuleAssignment",
        related_name="assigned_commission_rules",
        blank=True,
    )

    class Meta:
        ordering = ["priority", "sequence", "id"]

    def __str__(self):
        return self.name


class EmployeeCommissionRuleAssignment(models.Model):
    """Explicit link: a commission rule only evaluates for assigned employees."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="commission_rule_assignments",
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="commission_rule_assignments",
    )
    rule = models.ForeignKey(
        CommissionRule,
        on_delete=models.CASCADE,
        related_name="employee_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_rule_assignments_made",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "rule"],
                name="uniq_employee_commission_rule",
            )
        ]
        indexes = [
            models.Index(fields=["employee", "rule"], name="emprule_emp_rule_idx"),
            models.Index(fields=["organization", "rule"], name="emprule_org_rule_idx"),
        ]
        ordering = ["-assigned_at", "-id"]

    def __str__(self):
        return f"{self.employee_id} → rule {self.rule_id}"


class CommissionRuleCondition(models.Model):
    """Conditions combine with the rule's AND / OR logic to gate its results."""

    FIELD_CHOICES = [
        ("region", "Region"),
        ("product_name", "Product"),
        ("product_category", "Product Category"),
        ("service_name", "Service"),
        ("distribution", "Distribution"),
        ("customer_segment", "Customer Segment"),
        ("customer_type", "Customer Type"),
        ("business_group", "Business Unit"),
        ("department", "Department"),
        ("order_status", "Order Status"),
        ("currency", "Currency"),
        ("position_name", "Position Name"),
        ("employee_id", "Employee ID"),
        ("sales_amount", "Sales Amount"),
        ("revenue", "Revenue"),
        ("margin", "Margin"),
        ("achievement_pct", "Achievement %"),
        ("quota_pct", "Quota %"),
        ("territory_code", "Territory Code"),
        ("territory", "Territory"),
        ("role", "Role"),
        ("sales_channel", "Sales Channel"),
        ("order_date", "Order Date"),
        ("plan_basis", "Plan Basis"),
    ]
    OPERATOR_CHOICES = [
        ("eq", "Equals"),
        ("neq", "Not equals"),
        ("in", "In list"),
        ("contains", "Contains"),
        ("gt", "Greater than"),
        ("gte", "Greater or equal"),
        ("lt", "Less than"),
        ("lte", "Less or equal"),
        ("between", "Between (comma separated)"),
        ("empty", "Is empty"),
        ("not_empty", "Is not empty"),
    ]

    rule = models.ForeignKey(
        CommissionRule,
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    field = models.CharField(max_length=50, choices=FIELD_CHOICES)
    operator = models.CharField(max_length=20, choices=OPERATOR_CHOICES, default="eq")
    value = models.CharField(max_length=500, blank=True, default="")
    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.rule.name}: {self.field} {self.operator}"


class CommissionRuleResult(models.Model):
    """Outcome applied when rule conditions match."""

    CLASSIFICATION_CHOICES = [
        ("commission", "Commission"),
        ("credit", "Credit"),
        ("bonus", "Bonus"),
        ("spiff", "SPIFF"),
        ("draw", "Draw"),
        ("override", "Override"),
    ]
    RATE_TYPE_CHOICES = [
        ("override_tier_pct", "Override Tier %"),
        ("flat_amount", "Flat Amount"),
        ("percentage", "Percentage"),
        ("multiplier", "Multiplier"),
        ("override", "Override Amount"),
        ("add_bonus", "Add Bonus"),
    ]
    VALUE_UNIT_CHOICES = [
        ("currency", "Currency"),
        ("percent", "Percent"),
        ("units", "Units"),
        ("quota_pct", "Percent of Quota"),
    ]
    QUOTA_PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
    ]
    HOLD_PERIOD_CHOICES = [
        ("none", "None"),
        ("30_days", "30 Days"),
        ("60_days", "60 Days"),
        ("90_days", "90 Days"),
        ("until_paid", "Until Paid"),
    ]
    EARNING_GROUP_CHOICES = [
        ("base", "Base Commission"),
        ("bonus", "Bonus"),
        ("spiff", "SPIFF"),
        ("adjustment", "Adjustment"),
    ]

    rule = models.ForeignKey(
        CommissionRule,
        on_delete=models.CASCADE,
        related_name="results",
    )
    result_name = models.CharField(max_length=255, default="Result")
    hold_period = models.CharField(
        max_length=32,
        choices=HOLD_PERIOD_CHOICES,
        default="none",
    )
    result_classification = models.CharField(
        max_length=32,
        choices=CLASSIFICATION_CHOICES,
        default="commission",
    )
    quota_enabled = models.BooleanField(default=False)
    quota_period = models.CharField(
        max_length=32,
        choices=QUOTA_PERIOD_CHOICES,
        blank=True,
        default="",
    )
    result_rate_type = models.CharField(
        max_length=32,
        choices=RATE_TYPE_CHOICES,
        default="percentage",
    )
    rate_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    minimum_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    maximum_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    earning_group = models.CharField(
        max_length=32,
        choices=EARNING_GROUP_CHOICES,
        default="base",
    )
    value_unit_type = models.CharField(
        max_length=32,
        choices=VALUE_UNIT_CHOICES,
        default="currency",
    )
    reason_code = models.CharField(max_length=100, blank=True, default="")
    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.rule.name}: {self.result_name}"


# ---------------------------------------------------------------------------
# Phase 1.3 — Authentication hardening
# ---------------------------------------------------------------------------


class LoginEvent(models.Model):
    OUTCOME_SUCCESS = "success"
    OUTCOME_FAILED = "failed"
    OUTCOME_LOCKED = "locked"
    OUTCOME_MFA_REQUIRED = "mfa_required"
    OUTCOME_MFA_FAILED = "mfa_failed"
    OUTCOME_CHOICES = [
        (OUTCOME_SUCCESS, "Success"),
        (OUTCOME_FAILED, "Failed"),
        (OUTCOME_LOCKED, "Locked out"),
        (OUTCOME_MFA_REQUIRED, "MFA required"),
        (OUTCOME_MFA_FAILED, "MFA failed"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="login_events",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_events",
    )
    email = models.EmailField(db_index=True, blank=True, default="")
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")
    device_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    suspicious = models.BooleanField(default=False, db_index=True)
    suspicion_reason = models.CharField(max_length=255, blank=True, default="")
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_history",
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "password histories"


class TrustedDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
        null=True,
        blank=True,
    )
    device_id = models.CharField(max_length=64, db_index=True)
    device_name = models.CharField(max_length=120, blank=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    trusted_until = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="uniq_trusted_device_per_user",
            ),
        ]


class UserMfaDevice(models.Model):
    TYPE_TOTP = "totp"
    TYPE_CHOICES = [(TYPE_TOTP, "Authenticator app (TOTP)")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mfa_devices",
    )
    device_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TOTP)
    name = models.CharField(max_length=100, blank=True, default="Authenticator")
    secret_encrypted = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]


class UserAuthSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_sessions",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="auth_sessions",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=64, unique=True, db_index=True)
    token_key_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")
    device_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]


class Report(models.Model):
    """Saved self-service report definition (metadata-driven)."""

    DATASOURCE_COMMISSIONS = "commissions"
    DATASOURCE_ORDERS = "orders"
    DATASOURCE_EMPLOYEES = "employees"
    DATASOURCE_PLANS = "plans"
    DATASOURCE_PAYOUTS = "payouts"
    DATASOURCE_QUOTAS = "quotas"
    DATASOURCE_AUDIT = "audit_logs"
    DATASOURCE_CHOICES = [
        (DATASOURCE_COMMISSIONS, "Commission Records"),
        (DATASOURCE_ORDERS, "Orders"),
        (DATASOURCE_EMPLOYEES, "Employees"),
        (DATASOURCE_PLANS, "Compensation Plans"),
        (DATASOURCE_PAYOUTS, "Payouts"),
        (DATASOURCE_QUOTAS, "Quotas"),
        (DATASOURCE_AUDIT, "Audit Logs"),
    ]

    VIZ_TABLE = "table"
    VIZ_BAR = "bar"
    VIZ_LINE = "line"
    VIZ_PIE = "pie"
    VIZ_CHOICES = [
        (VIZ_TABLE, "Table"),
        (VIZ_BAR, "Bar chart"),
        (VIZ_LINE, "Line chart"),
        (VIZ_PIE, "Pie chart"),
    ]

    VISIBILITY_PRIVATE = "private"
    VISIBILITY_ORG = "organization"
    VISIBILITY_ROLE = "role"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, "Private"),
        (VISIBILITY_ORG, "Organization"),
        (VISIBILITY_ROLE, "Role-restricted"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    report_type = models.CharField(
        max_length=32,
        choices=DATASOURCE_CHOICES,
        default=DATASOURCE_COMMISSIONS,
        db_index=True,
    )
    visualization = models.CharField(
        max_length=16, choices=VIZ_CHOICES, default=VIZ_TABLE
    )
    group_by = models.CharField(max_length=64, blank=True, default="")
    sort_by = models.CharField(max_length=64, blank=True, default="")
    sort_dir = models.CharField(max_length=4, default="desc")  # asc|desc
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE
    )
    allowed_roles = models.JSONField(default=list, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_reports",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["organization", "-updated_at"]),
            models.Index(fields=["organization", "report_type"]),
        ]

    def __str__(self):
        return self.name


class ReportField(models.Model):
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="fields"
    )
    field_key = models.CharField(max_length=64)
    label = models.CharField(max_length=128, blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    aggregation = models.CharField(
        max_length=16, blank=True, default=""
    )  # sum|avg|count|min|max|""

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("report", "field_key")


class ReportFilter(models.Model):
    OP_EQ = "eq"
    OP_NE = "ne"
    OP_CONTAINS = "contains"
    OP_GTE = "gte"
    OP_LTE = "lte"
    OP_IN = "in"
    OP_BETWEEN = "between"
    OP_CHOICES = [
        (OP_EQ, "Equals"),
        (OP_NE, "Not equals"),
        (OP_CONTAINS, "Contains"),
        (OP_GTE, "Greater or equal"),
        (OP_LTE, "Less or equal"),
        (OP_IN, "In list"),
        (OP_BETWEEN, "Between"),
    ]

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="filters"
    )
    field_key = models.CharField(max_length=64)
    operator = models.CharField(max_length=16, choices=OP_CHOICES, default=OP_EQ)
    value = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]


class ReportSchedule(models.Model):
    FREQ_DAILY = "daily"
    FREQ_WEEKLY = "weekly"
    FREQ_MONTHLY = "monthly"
    FREQ_CHOICES = [
        (FREQ_DAILY, "Daily"),
        (FREQ_WEEKLY, "Weekly"),
        (FREQ_MONTHLY, "Monthly"),
    ]

    DELIVERY_EMAIL_PDF = "email_pdf"
    DELIVERY_EMAIL_EXCEL = "email_excel"
    DELIVERY_DOWNLOAD = "download"
    DELIVERY_CHOICES = [
        (DELIVERY_EMAIL_PDF, "Email PDF"),
        (DELIVERY_EMAIL_EXCEL, "Email Excel"),
        (DELIVERY_DOWNLOAD, "Download"),
    ]

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="schedules"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="report_schedules",
        null=True,
        blank=True,
    )
    frequency = models.CharField(
        max_length=16, choices=FREQ_CHOICES, default=FREQ_WEEKLY
    )
    delivery = models.CharField(
        max_length=16, choices=DELIVERY_CHOICES, default=DELIVERY_EMAIL_EXCEL
    )
    recipients = models.JSONField(default=list, blank=True)
    timezone_name = models.CharField(max_length=64, blank=True, default="UTC")
    is_active = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_report_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


# =====================================================
# Compensation Document Repository (governance)
# =====================================================


class CompensationDocument(models.Model):
    """Logical compensation document (versioned; never overwritten)."""

    TYPE_COMP_PLAN = "compensation_plan"
    TYPE_COMMISSION_POLICY = "commission_policy"
    TYPE_QUOTA_LETTER = "quota_letter"
    TYPE_EMPLOYEE_AGREEMENT = "employee_agreement"
    TYPE_APPROVAL = "approval_document"
    TYPE_EXCEPTION = "exception_approval"
    TYPE_OTHER = "other"
    TYPE_CHOICES = (
        (TYPE_COMP_PLAN, "Compensation Plan"),
        (TYPE_COMMISSION_POLICY, "Commission Policy"),
        (TYPE_QUOTA_LETTER, "Quota Letter"),
        (TYPE_EMPLOYEE_AGREEMENT, "Employee Agreement"),
        (TYPE_APPROVAL, "Approval Document"),
        (TYPE_EXCEPTION, "Exception Approval"),
        (TYPE_OTHER, "Other"),
    )

    STATUS_DRAFT = "draft"
    STATUS_PENDING_REVIEW = "pending_review"
    STATUS_APPROVED = "approved"
    STATUS_PUBLISHED = "published"
    STATUS_ACTIVE = "published"  # legacy alias
    STATUS_EXPIRED = "expired"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING_REVIEW, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_ARCHIVED, "Archived"),
    )

    APPROVAL_NOT_STARTED = "not_started"
    APPROVAL_PENDING = "pending"
    APPROVAL_IN_REVIEW = "in_review"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_STATUS_CHOICES = (
        (APPROVAL_NOT_STARTED, "Not started"),
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_IN_REVIEW, "In review"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="compensation_documents",
        db_index=True,
    )
    name = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=40, choices=TYPE_CHOICES, default=TYPE_OTHER, db_index=True
    )
    related_plan = models.ForeignKey(
        "CompensationPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    linked_rules = models.ManyToManyField(
        "CommissionRule",
        blank=True,
        related_name="supporting_documents",
    )
    business_unit = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True
    )
    current_version = models.ForeignKey(
        "CompensationDocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approval_required = models.BooleanField(default=True)
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default=APPROVAL_NOT_STARTED,
        db_index=True,
    )
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_compensation_documents",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_compensation_documents",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_compensation_documents",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_compensation_documents",
    )
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def touch_activity(self, save=True):
        self.last_activity_at = timezone.now()
        if save:
            self.save(update_fields=["last_activity_at", "updated_at"])

    def refresh_lifecycle(self, save=True):
        """Derive lifecycle from dates/approval without overriding archived."""
        if self.status == self.STATUS_ARCHIVED:
            return self.status
        today = date.today()
        cv = self.current_version
        if cv and cv.effective_to and cv.effective_to < today:
            self.status = self.STATUS_EXPIRED
        elif self.approval_status in (
            self.APPROVAL_PENDING,
            self.APPROVAL_IN_REVIEW,
        ) or (
            cv and cv.approval_status == CompensationDocumentVersion.APPROVAL_PENDING
        ):
            self.status = self.STATUS_PENDING_REVIEW
        elif self.status in (self.STATUS_APPROVED, self.STATUS_PUBLISHED) or (
            self.approval_status == self.APPROVAL_APPROVED
        ):
            if cv and cv.effective_from and cv.effective_from > today:
                self.status = self.STATUS_APPROVED
            elif self.status != self.STATUS_DRAFT:
                self.status = self.STATUS_PUBLISHED
        if save:
            self.save(update_fields=["status", "updated_at"])
        return self.status

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["organization", "status", "-updated_at"],
                name="compdoc_org_status_upd_idx",
            ),
            models.Index(
                fields=["organization", "document_type"],
                name="compdoc_org_type_idx",
            ),
            models.Index(
                fields=["organization", "related_plan"],
                name="compdoc_org_plan_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization_id})"


class CompensationDocumentVersion(models.Model):
    """Immutable file version for a compensation document."""

    APPROVAL_PENDING = "pending"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"
    APPROVAL_NOT_REQUIRED = "not_required"
    APPROVAL_CHOICES = (
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
        (APPROVAL_NOT_REQUIRED, "Not required"),
    )

    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    )

    document = models.ForeignKey(
        CompensationDocument,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField(default=1)
    version_label = models.CharField(max_length=32, blank=True, default="")
    file = models.FileField(upload_to="compensation_docs/%Y/%m/", blank=True)
    storage_backend = models.CharField(max_length=32, default="local", blank=True)
    storage_key = models.CharField(max_length=512, blank=True, default="")
    file_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True
    )
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_NOT_REQUIRED,
        db_index=True,
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_to_approve",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_document_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number", "-created_at"]
        unique_together = (("document", "version_number"),)
        indexes = [
            models.Index(
                fields=["document", "-version_number"],
                name="compdocver_doc_ver_idx",
            ),
        ]

    def __str__(self):
        return f"{self.document_id} v{self.version_number}"

    @property
    def display_version(self):
        return self.version_label or f"v{self.version_number}"


# ---------------------------------------------------------------------------
# Employee compensation overrides
#
# Compensation Plan -> Commission Rules -> Employee Assignment ->
# Employee Override (optional) -> Commission Calculation.
#
# Overrides are exceptions layered on top of an assigned plan. They never
# replace the plan, so one plan can still serve thousands of employees.
# ---------------------------------------------------------------------------


class EmployeeCompensationOverride(models.Model):
    """An employee-specific exception to their assigned compensation plan."""

    TYPE_COMMISSION_RATE = "commission_rate"
    TYPE_BONUS = "bonus"
    TYPE_ACCELERATOR = "accelerator"
    TYPE_MULTIPLIER = "multiplier"
    TYPE_QUOTA = "quota"
    TYPE_ELIGIBILITY = "eligibility"
    TYPE_DRAW = "draw"
    TYPE_RECOVERY = "recovery"
    TYPE_CHOICES = [
        (TYPE_COMMISSION_RATE, "Commission Rate"),
        (TYPE_BONUS, "Bonus"),
        (TYPE_ACCELERATOR, "Accelerator"),
        (TYPE_MULTIPLIER, "Multiplier"),
        (TYPE_QUOTA, "Quota"),
        (TYPE_ELIGIBILITY, "Eligibility"),
        (TYPE_DRAW, "Draw"),
        (TYPE_RECOVERY, "Recovery"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending_approval"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending Approval"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_REVOKED, "Revoked"),
    ]

    UNIT_PERCENT = "percent"
    UNIT_CURRENCY = "currency"
    UNIT_MULTIPLIER = "multiplier"
    UNIT_UNITS = "units"
    UNIT_BOOLEAN = "boolean"
    UNIT_CHOICES = [
        (UNIT_PERCENT, "Percent"),
        (UNIT_CURRENCY, "Currency"),
        (UNIT_MULTIPLIER, "Multiplier"),
        (UNIT_UNITS, "Units"),
        (UNIT_BOOLEAN, "Yes / No"),
    ]

    DEFAULT_UNIT_FOR_TYPE = {
        TYPE_COMMISSION_RATE: UNIT_PERCENT,
        TYPE_ACCELERATOR: UNIT_PERCENT,
        TYPE_BONUS: UNIT_CURRENCY,
        TYPE_DRAW: UNIT_CURRENCY,
        TYPE_RECOVERY: UNIT_CURRENCY,
        TYPE_QUOTA: UNIT_CURRENCY,
        TYPE_MULTIPLIER: UNIT_MULTIPLIER,
        TYPE_ELIGIBILITY: UNIT_BOOLEAN,
    }

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="compensation_overrides",
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(
        "UserProfile",
        on_delete=models.CASCADE,
        related_name="compensation_overrides",
    )
    compensation_plan = models.ForeignKey(
        CompensationPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_overrides",
        help_text="Plan this override modifies. Blank means the employee's assigned plan.",
    )

    name = models.CharField(max_length=255)
    override_type = models.CharField(
        max_length=32,
        choices=TYPE_CHOICES,
        default=TYPE_COMMISSION_RATE,
        db_index=True,
    )
    value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    value_unit = models.CharField(
        max_length=20, choices=UNIT_CHOICES, default=UNIT_PERCENT
    )
    previous_value = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Plan value replaced by this override, captured at creation.",
    )

    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)
    reason = models.TextField(blank=True, default="")

    # Priority 1 by definition: overrides outrank every plan-owned rule.
    priority = models.PositiveIntegerField(default=1)
    stop_on_match = models.BooleanField(
        default=True,
        help_text="Skip plan rules of the same type once this override applies.",
    )

    approval_required = models.BooleanField(default=True)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compensation_overrides_to_approve",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compensation_overrides_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compensation_overrides_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "-effective_from", "-id"]
        indexes = [
            models.Index(
                fields=["employee", "status", "effective_from"],
                name="empoverride_emp_status_idx",
            ),
            models.Index(
                fields=["organization", "override_type", "status"],
                name="empoverride_org_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_override_type_display()})"

    def is_effective_on(self, on_date):
        if self.status != self.STATUS_APPROVED:
            return False
        if not on_date:
            return False
        if self.effective_from and on_date < self.effective_from:
            return False
        if self.effective_to and on_date > self.effective_to:
            return False
        return True

    @property
    def is_expired(self):
        from django.utils import timezone as _tz

        return bool(self.effective_to and self.effective_to < _tz.localdate())


class EmployeeCompensationOverrideEvent(models.Model):
    """Immutable history / audit trail for a single override."""

    EVENT_CREATED = "created"
    EVENT_UPDATED = "updated"
    EVENT_SUBMITTED = "submitted"
    EVENT_APPROVED = "approved"
    EVENT_REJECTED = "rejected"
    EVENT_EXPIRED = "expired"
    EVENT_REMOVED = "removed"
    EVENT_APPLIED = "applied"
    EVENT_CHOICES = [
        (EVENT_CREATED, "Override Created"),
        (EVENT_UPDATED, "Override Updated"),
        (EVENT_SUBMITTED, "Submitted For Approval"),
        (EVENT_APPROVED, "Override Approved"),
        (EVENT_REJECTED, "Override Rejected"),
        (EVENT_EXPIRED, "Override Expired"),
        (EVENT_REMOVED, "Override Removed"),
        (EVENT_APPLIED, "Override Applied To Commission"),
    ]

    override = models.ForeignKey(
        EmployeeCompensationOverride,
        on_delete=models.CASCADE,
        related_name="history",
    )
    # Kept denormalised so history survives if the override row is deleted
    # from a downstream copy of the data.
    override_name = models.CharField(max_length=255, blank=True, default="")
    event = models.CharField(max_length=32, choices=EVENT_CHOICES, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compensation_override_events",
    )
    reason = models.TextField(blank=True, default="")
    old_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    status_after = models.CharField(max_length=20, blank=True, default="")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.override_name or self.override_id}: {self.event}"
