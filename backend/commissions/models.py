from django.db import models
from django.conf import settings


class Organization(models.Model):
    """Tenant boundary for multi-company deployments."""

    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    STATUS_CHOICES = [
        (STATUS_CALCULATED, "Calculated"),
        (STATUS_MANAGER_APPROVED, "Manager approved"),
        (STATUS_APPROVED, "Finance approved"),
        (STATUS_PAID, "Paid"),
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


class AuditLog(models.Model):
    """Immutable trail of sensitive actions for pilot / compliance."""

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
    action = models.CharField(max_length=64, db_index=True)
    plan_version = models.ForeignKey(
        "CommissionPlanVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=36, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} ({self.user_email or 'system'})"


class ExternalIntegration(models.Model):
    """Third-party CRM / API connection for syncing users and orders."""

    PROVIDER_SALESFORCE = "salesforce"
    PROVIDER_GENERIC_REST = "generic_rest"
    PROVIDER_WEBHOOK = "webhook"
    PROVIDER_HUBSPOT = "hubspot"
    PROVIDER_ZOHO = "zoho"
    PROVIDER_CHOICES = [
        (PROVIDER_SALESFORCE, "Salesforce"),
        (PROVIDER_GENERIC_REST, "Generic REST API"),
        (PROVIDER_WEBHOOK, "Webhook / Zapier"),
        (PROVIDER_HUBSPOT, "HubSpot (REST)"),
        (PROVIDER_ZOHO, "Zoho CRM"),
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
    credentials = models.JSONField(default=dict, blank=True)
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

    sequence = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    stop_on_match = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return self.name


class CommissionRuleCondition(models.Model):
    """When all active conditions match, the rule results apply."""

    FIELD_CHOICES = [
        ("region", "Region"),
        ("product_name", "Product"),
        ("service_name", "Service"),
        ("distribution", "Distribution"),
        ("customer_segment", "Customer Segment"),
        ("business_group", "Business Group"),
        ("order_status", "Order Status"),
        ("currency", "Currency"),
        ("position_name", "Position Name"),
        ("employee_id", "Employee ID"),
        ("sales_amount", "Sales Amount"),
        ("territory_code", "Territory Code"),
        ("role", "Role"),
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
