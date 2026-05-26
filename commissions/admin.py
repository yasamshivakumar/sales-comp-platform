from django.contrib import admin
from .models import Employee,Sale,Commission,IncentiveRule

admin.site.register(Employee)
admin.site.register(Sale)
admin.site.register(IncentiveRule)
from .models import CompensationPlan, CompensationTier
from .models import CompensationPlan, SCRateTable, SCFlatRateTable


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
    ]


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

class CommissionAdmin(admin.ModelAdmin):
    readonly_fields = ('employee', 'sale', 'commission_amount')

    def has_add_permission(self, request):
        return False


admin.site.register(Commission, CommissionAdmin)