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

    name = models.CharField(max_length=100)

    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name


class Sale(models.Model):

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


class Commission(models.Model):
    STATUS_CALCULATED = "calculated"
    STATUS_APPROVED = "approved"
    STATUS_CHOICES = [
        (STATUS_CALCULATED, "Calculated"),
        (STATUS_APPROVED, "Approved"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_index=True
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

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CALCULATED,
        db_index=True,
    )

    calculated_at = models.DateTimeField(auto_now_add=True, null=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_commissions",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status", "calculated_at"]),
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
    ]

    commission_table_type = models.CharField(
        max_length=10,
        choices=COMMISSION_TABLE_TYPE_CHOICES,
        default='RATE',
        help_text='Select which commission table type this plan uses.'
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
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

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
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=36, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} ({self.user_email or 'system'})"
