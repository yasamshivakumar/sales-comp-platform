from django.db import models
from django.contrib.auth.models import AbstractUser


# class User(AbstractUser):
#     """Custom User model extending Django's AbstractUser"""
#     ROLE_CHOICES = [
#         ('admin', 'Admin'),
#         ('manager', 'Manager'),
#         ('sales_rep', 'Sales Representative'),
#         ('finance', 'Finance'),
#         ('viewer', 'Viewer'),
#     ]
    
#     role = models.CharField(
#         max_length=50,
#         choices=ROLE_CHOICES,
#         default='sales_rep',
#         help_text='User role for the compensation platform'
#     )
    
#     employee_id = models.CharField(
#         max_length=100,
#         blank=True,
#         null=True,
#         unique=True,
#         help_text='External employee ID'
#     )
    
#     is_active_user = models.BooleanField(
#         default=True,
#         help_text='Whether user can access the platform'
#     )
    
#     phone = models.CharField(
#         max_length=20,
#         blank=True,
#         null=True
#     )
    
#     department = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ['date_joined']

#     def __str__(self):
#         return f"{self.get_full_name() or self.username} ({self.role})"


class Employee(models.Model):

    name = models.CharField(max_length=100)

    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name


class Sale(models.Model):

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

    def __str__(self):
        return f"{self.employee.name} - {self.commission_amount}"


class IncentiveRule(models.Model):

    min_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    max_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.min_amount} - {self.max_amount} : {self.percentage}%"



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

    # Basic Information
    plan_name = models.CharField(
        max_length=200,
        unique=True
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
    # User Section
    enable_login = models.BooleanField(default=False)
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, db_index=True)
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
        unique=False
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
    # Transaction identifiers
    order_id = models.CharField(max_length=100, unique=True)
    order_date = models.DateField()

    # Participant references
    employee_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    position_name = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    # Business context
    # customer_name = models.CharField(max_length=200, blank=True, null=True)
    # product_name = models.CharField(max_length=200, blank=True, null=True)
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

    def __str__(self):
        return f"{self.order_id} - {self.sales_amount}"


# create django model for commission table
