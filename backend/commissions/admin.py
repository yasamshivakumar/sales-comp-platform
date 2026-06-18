from django.contrib import admin
from .models import (
    Employee,
    Sale,
    Commission,

    UserProfile,
    Order,
    AuditLog,
    Organization,
    ImportJob,
    Territory,
    PayoutRun,
    CommissionDispute,
    ExternalIntegration,
    IntegrationSyncLog,
)

admin.site.register(Organization)
admin.site.register(ImportJob)
admin.site.register(Employee)
admin.site.register(Sale)
admin.site.register(UserProfile)
admin.site.register(Order)

from .models import CompensationPlan, CompensationTier, SCRateTable, SCFlatRateTable, SCLookupTable
from .models import CommissionRule, CommissionRuleCondition, CommissionRuleResult


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


class SCLookupTableInline(admin.TabularInline):
    model = SCLookupTable
    extra = 1
    fields = (
        "tier_name",
        "product_name",
        "service_name",
        "distribution",
        "from_amount",
        "to_amount",
        "commission_rate",
        "bonus_amount",
        "sequence",
        "is_active",
    )
    ordering = ["sequence", "from_amount"]


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
        SCRateTableInline,
        SCFlatRateTableInline,
        SCLookupTableInline,
    ]


class CommissionRuleConditionInline(admin.TabularInline):
    model = CommissionRuleCondition
    extra = 1


class CommissionRuleResultInline(admin.TabularInline):
    model = CommissionRuleResult
    extra = 1


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "compensation_plan", "rule_type", "sequence", "is_active")
    list_filter = ("rule_type", "is_active")
    search_fields = ("name", "compensation_plan__plan_name")
    inlines = [CommissionRuleConditionInline, CommissionRuleResultInline]


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
    list_display = ("action", "user_email", "ip_address", "created_at")
    list_filter = ("action",)
    search_fields = ("user_email", "action", "request_id")
    readonly_fields = (
        "user",
        "user_email",
        "action",
        "detail",
        "ip_address",
        "request_id",
        "created_at",
    )


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


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "code")


@admin.register(PayoutRun)
class PayoutRunAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "start_date", "end_date", "payment_reference", "paid_at")
    list_filter = ("status",)
    search_fields = ("name", "payment_reference")


@admin.register(CommissionDispute)
class CommissionDisputeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "commission",
        "status",
        "raised_by",
        "employee_acknowledged_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("message", "commission__employee__name")


@admin.register(ExternalIntegration)
class ExternalIntegrationAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "organization", "is_active", "last_user_sync_at", "last_order_sync_at")
    list_filter = ("provider", "is_active")
    search_fields = ("name",)
    readonly_fields = ("webhook_secret", "created_at", "updated_at")


@admin.register(IntegrationSyncLog)
class IntegrationSyncLogAdmin(admin.ModelAdmin):
    list_display = ("integration", "sync_type", "status", "records_fetched", "started_at")
    list_filter = ("sync_type", "status")
    readonly_fields = ("started_at", "completed_at")