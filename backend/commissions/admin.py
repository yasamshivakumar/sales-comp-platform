from django.contrib import admin
from .models import (
    Employee,
    Sale,
    Commission,
    CommissionAdjustment,
    UserProfile,
    Order,
    AuditLog,
    Organization,
    ImportJob,
)

admin.site.register(Organization)
admin.site.register(ImportJob)
admin.site.register(Employee)
admin.site.register(Sale)
admin.site.register(UserProfile)
admin.site.register(Order)
admin.site.register(CommissionAdjustment)

from .models import CompensationPlan, CompensationTier
from .models import CompensationPlan, SCRateTable, SCFlatRateTable
from .models import CommissionPlanVersion, PlanVersionQuota


# ---------------------------------------------------
# Inline for Tier-Based Rate Table
# ---------------------------------------------------
class SCRateTableInline(admin.TabularInline):
    model = SCRateTable
    extra = 1
    fields = (
        'tier_name',
        'from_amount',
        'to_amount',
        'commission_rate',
        'bonus_amount',
        'sequence',
        'is_active'
    )
    ordering = ['sequence', 'from_amount']


# ---------------------------------------------------
# Inline for Flat Rate Table
# ---------------------------------------------------
class SCFlatRateTableInline(admin.TabularInline):
    model = SCFlatRateTable
    extra = 1
    fields = (
        'flat_rate',
        'bonus_amount',
        'minimum_sales_threshold',
        'is_active'
    )


class PlanVersionInline(admin.TabularInline):
    model = CommissionPlanVersion
    extra = 0
    fields = (
        "version_number",
        "status",
        "effective_from",
        "effective_to",
        "published_at",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True


# ---------------------------------------------------
# Compensation Plan Admin
# ---------------------------------------------------
@admin.register(CompensationPlan)
class CompensationPlanAdmin(admin.ModelAdmin):
    # Removed basis_value because that field no longer exists
    list_display = (
        'plan_name',
        'plan_basis',
        'position_name',
        'role',
        'status',
        'effective_start_date',
        'pay_period_type',
        'created_at',
    )

    list_filter = (
        'status',
        'plan_basis',
        'pay_period_type',
        'role',
        'business_group',
    )

    search_fields = (
        'plan_name',
        'position_name',
        'role',
        'title',
        'business_group',
    )

    inlines = [
        PlanVersionInline,
        SCRateTableInline,
        SCFlatRateTableInline,
    ]


@admin.register(CommissionPlanVersion)
class CommissionPlanVersionAdmin(admin.ModelAdmin):
    list_display = (
        "compensation_plan",
        "version_number",
        "status",
        "effective_from",
        "effective_to",
        "published_at",
        "organization",
    )
    list_filter = ("status", "commission_table_type", "organization")
    search_fields = (
        "compensation_plan__plan_name",
        "description",
        "position_name",
        "role",
    )
    readonly_fields = ("published_at", "published_by", "created_at", "updated_at")


@admin.register(PlanVersionQuota)
class PlanVersionQuotaAdmin(admin.ModelAdmin):
    list_display = ("plan_version", "year", "month", "quota_amount", "currency")
    list_filter = ("year", "month")
    search_fields = ("plan_version__compensation_plan__plan_name",)


# ---------------------------------------------------
# Optional: Register child tables separately
# ---------------------------------------------------
@admin.register(SCRateTable)
class SCRateTableAdmin(admin.ModelAdmin):
    list_display = (
        'compensation_plan',
        'tier_name',
        'from_amount',
        'to_amount',
        'commission_rate',
        'bonus_amount',
        'sequence',
        'is_active',
        'created_at',
    )

    list_filter = (
        'is_active',
        'compensation_plan',
        'created_at',
    )

    search_fields = (
        'tier_name',
        'compensation_plan__plan_name',
    )

    fieldsets = (
        ('Plan Information', {
            'fields': ('compensation_plan',)
        }),
        ('Tier Details', {
            'fields': (
                'tier_name',
                'sequence',
            )
        }),
        ('Sales Range', {
            'fields': (
                'from_amount',
                'to_amount',
            ),
            'description': 'Define the sales amount range. Leave "to_amount" blank for no upper limit.'
        }),
        ('Commission Settings', {
            'fields': (
                'commission_rate',
                'bonus_amount',
            ),
            'description': 'Commission rate as percentage (e.g., 5.00 = 5%)'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    readonly_fields = ('created_at',)
    ordering = ('compensation_plan', 'sequence', 'from_amount')


@admin.register(SCFlatRateTable)
class SCFlatRateTableAdmin(admin.ModelAdmin):
    list_display = (
        'compensation_plan',
        'flat_rate',
        'bonus_amount',
        'minimum_sales_threshold',
        'is_active',
        'created_at',
    )

    list_filter = (
        'is_active',
        'compensation_plan',
        'created_at',
    )

    search_fields = (
        'compensation_plan__plan_name',
    )

    fieldsets = (
        ('Plan Information', {
            'fields': ('compensation_plan',)
        }),
        ('Flat Commission Settings', {
            'fields': (
                'flat_rate',
                'bonus_amount',
            ),
            'description': 'Set a flat commission rate (percentage) that applies to all sales.'
        }),
        ('Sales Threshold', {
            'fields': ('minimum_sales_threshold',),
            'description': 'Minimum sales amount required to trigger this commission.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    readonly_fields = ('created_at',)
    ordering = ('compensation_plan',)


@admin.register(CompensationTier)
class CompensationTierAdmin(admin.ModelAdmin):
    list_display = (
        'plan',
        'tier_name',
        'min_sales',
        'max_sales',
        'commission_percent',
        'bonus_amount',
        'is_active',
    )

    list_filter = (
        'is_active',
        'plan',
    )

    search_fields = (
        'plan__plan_name',
        'tier_name',
    )

    ordering = (
        'plan',
        'min_sales',
    )


# ---------------------------------------------------
# Commission Admin - Now Fully Visible
# ---------------------------------------------------
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "module",
        "severity",
        "status",
        "user_email",
        "ip_address",
        "created_at",
    )
    list_filter = ("module", "severity", "status", "source", "action")
    search_fields = ("user_email", "action", "request_id", "employee_id", "search_text")
    readonly_fields = (
        "organization",
        "user",
        "user_email",
        "employee_id",
        "role",
        "business_unit",
        "action",
        "module",
        "entity_type",
        "entity_id",
        "severity",
        "source",
        "status",
        "plan_version",
        "detail",
        "reason",
        "old_value",
        "new_value",
        "changed_fields",
        "duration_ms",
        "ip_address",
        "user_agent",
        "device",
        "session_id",
        "request_id",
        "search_text",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'employee_name',
        'employee_email',
        'commission_amount',
        'sale',
    )

    list_filter = (
        'commission_amount',
    )

    search_fields = (
        'employee__name',
        'employee__email',
        'sale__id',
    )

    readonly_fields = (
        'id',
        'employee',
        'sale',
        'commission_amount',
    )

    def employee_name(self, obj):
        return obj.employee.name if obj.employee else "Unknown"
    employee_name.short_description = 'Employee Name'

    def employee_email(self, obj):
        return obj.employee.email if obj.employee else "N/A"
    employee_email.short_description = 'Employee Email'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False