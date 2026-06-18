from rest_framework import serializers
from .models import Employee, Commission, UserProfile, HierarchyRelationship, CompensationTier, Order

from .models import (
    CompensationPlan,
    SCRateTable,
    SCFlatRateTable,
    SCLookupTable,
    Territory,
    PayoutRun,
    CommissionDispute,
    ExternalIntegration,
    IntegrationSyncLog,
    CommissionRule,
    CommissionRuleCondition,
    CommissionRuleResult,
)
class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'


class CommissionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    employee_id = serializers.SerializerMethodField()
    order_id = serializers.SerializerMethodField()
    order_date = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    plan_name = serializers.CharField(
        source='compensation_plan.plan_name',
        read_only=True,
        default=None,
    )
    approved_by_email = serializers.EmailField(
        source='approved_by.email',
        read_only=True,
        default=None,
    )
    manager_approved_by_email = serializers.EmailField(
        source='manager_approved_by.email',
        read_only=True,
        default=None,
    )
    has_open_dispute = serializers.SerializerMethodField()

    class Meta:
        model = Commission
        fields = '__all__'
        read_only_fields = [
            'calculated_at',
            'manager_approved_at',
            'manager_approved_by',
            'approved_at',
            'approved_by',
            'paid_at',
            'payout_run',
            'compensation_plan',
            'status',
        ]

    def get_has_open_dispute(self, obj):
        return obj.disputes.filter(status=CommissionDispute.STATUS_OPEN).exists()

    def get_order_id(self, obj):
        order = getattr(obj.sale, 'order', None) if obj.sale_id else None
        return order.order_id if order else None

    def get_order_date(self, obj):
        order = getattr(obj.sale, 'order', None) if obj.sale_id else None
        return order.order_date if order else None

    def get_employee_id(self, obj):
        # Try to get employee_id from UserProfile if available
        try:
            user_profile = UserProfile.objects.get(email=obj.employee.email)
            return user_profile.employee_id
        except UserProfile.DoesNotExist:
            # Fallback: return a derived ID from employee email if no profile
            return obj.employee.email.split('@')[0]

    def get_currency(self, obj):
        from .currencies import normalize_currency

        order = getattr(obj.sale, "order", None) if obj.sale_id else None
        return normalize_currency(getattr(order, "currency", None))

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'

    def validate(self, attrs):
        from .currencies import normalize_currency
        from .field_rules import validate_user_profile_fields

        raw = getattr(self, "initial_data", None) or {}
        if hasattr(raw, "dict"):
            raw = raw.dict()
        merged = {**raw, **attrs}
        validate_user_profile_fields(merged, partial=self.partial)
        if "personal_currency" in merged:
            attrs["personal_currency"] = normalize_currency(merged.get("personal_currency"))
        return attrs

class HierarchyRelationshipSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(
        source='parent_participant.first_name',
        read_only=True
    )

    child_name = serializers.CharField(
        source='child_participant.first_name',
        read_only=True
    )

    class Meta:
        model = HierarchyRelationship
        fields = '__all__'


class CompensationTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompensationTier
        fields = '__all__'

# ------------------------------------------
# SC Rate Table Serializer
# ------------------------------------------
class SCRateTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCRateTable
        fields = '__all__'
        read_only_fields = ['compensation_plan']


# ------------------------------------------
# SC Flat Rate Table Serializer
# ------------------------------------------
class SCFlatRateTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCFlatRateTable
        fields = '__all__'
        read_only_fields = ['compensation_plan']


class SCLookupTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCLookupTable
        fields = '__all__'
        read_only_fields = ['compensation_plan']


class CommissionRuleConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionRuleCondition
        fields = "__all__"
        read_only_fields = ["rule"]


class CommissionRuleResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionRuleResult
        fields = "__all__"
        read_only_fields = ["rule"]


class CommissionRuleSerializer(serializers.ModelSerializer):
    conditions = CommissionRuleConditionSerializer(many=True, required=False)
    results = CommissionRuleResultSerializer(many=True, required=False)
    plan_name = serializers.CharField(
        source="compensation_plan.plan_name",
        read_only=True,
        default=None,
    )

    class Meta:
        model = CommissionRule
        fields = "__all__"
        read_only_fields = ["organization", "created_at", "updated_at"]

    def _sync_children(self, rule, conditions=None, results=None):
        if conditions is not None:
            rule.conditions.all().delete()
            for row in conditions:
                CommissionRuleCondition.objects.create(rule=rule, **row)
        if results is not None:
            rule.results.all().delete()
            for row in results:
                CommissionRuleResult.objects.create(rule=rule, **row)

    def create(self, validated_data):
        conditions = validated_data.pop("conditions", [])
        results = validated_data.pop("results", [])
        rule = CommissionRule.objects.create(**validated_data)
        self._sync_children(rule, conditions, results)
        return rule

    def update(self, instance, validated_data):
        conditions = validated_data.pop("conditions", None)
        results = validated_data.pop("results", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if conditions is not None or results is not None:
            self._sync_children(
                instance,
                conditions if conditions is not None else None,
                results if results is not None else None,
            )
        return instance


# ------------------------------------------
# Compensation Plan Serializer
# ------------------------------------------
class CompensationPlanSerializer(serializers.ModelSerializer):
    sc_rate_tables = SCRateTableSerializer(
        many=True,
        required=False
    )

    sc_flat_rate_tables = SCFlatRateTableSerializer(
        many=True,
        required=False
    )

    sc_lookup_tables = SCLookupTableSerializer(
        many=True,
        required=False,
    )

    commission_rules = CommissionRuleSerializer(
        many=True,
        required=False,
        read_only=True,
    )

    class Meta:
        model = CompensationPlan
        fields = '__all__'
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "effective_start_date": {"required": False, "allow_null": True},
            "effective_end_date": {"required": False, "allow_null": True},
            "position_name": {"required": False, "allow_blank": True, "allow_null": True},
            "title": {"required": False, "allow_blank": True, "allow_null": True},
            "business_group": {"required": False, "allow_blank": True, "allow_null": True},
            "pay_period_type": {"required": False},
            "role": {"required": False, "allow_blank": True},
            "commission_table_type": {"required": False},
        }

    def validate(self, attrs):
        from .field_rules import (
            normalize_compensation_plan_payload,
            validate_compensation_plan_fields,
        )

        raw = getattr(self, "initial_data", None) or {}
        if hasattr(raw, "dict"):
            raw = raw.dict()
        merged = normalize_compensation_plan_payload({**raw, **attrs})
        validate_compensation_plan_fields(merged, partial=self.partial)

        # Drop UI-only aliases before model create/update.
        merged.pop("comp_period", None)
        merged.pop("plan_month", None)
        merged.pop("table_type", None)

        return merged

    # --------------------------------------
    # Create plan and child tables
    # --------------------------------------
    def create(self, validated_data):
        rate_tables = validated_data.pop(
            'sc_rate_tables',
            []
        )

        flat_rate_tables = validated_data.pop(
            'sc_flat_rate_tables',
            []
        )

        lookup_tables = validated_data.pop(
            'sc_lookup_tables',
            [],
        )

        # Create Compensation Plan
        plan = CompensationPlan.objects.create(
            **validated_data
        )

        # Create SC Rate Tables
        for row in rate_tables:
            SCRateTable.objects.create(
                compensation_plan=plan,
                **row
            )

        # Create SC Flat Rate Tables
        for row in flat_rate_tables:
            SCFlatRateTable.objects.create(
                compensation_plan=plan,
                **row
            )

        for row in lookup_tables:
            SCLookupTable.objects.create(
                compensation_plan=plan,
                **row,
            )

        return plan

    # --------------------------------------
    # Update plan and replace child tables
    # --------------------------------------
    def update(self, instance, validated_data):
        rate_tables = validated_data.pop(
            'sc_rate_tables',
            None
        )

        flat_rate_tables = validated_data.pop(
            'sc_flat_rate_tables',
            None
        )

        lookup_tables = validated_data.pop(
            'sc_lookup_tables',
            None,
        )

        # Update plan fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Replace rate tables
        if rate_tables is not None:
            instance.sc_rate_tables.all().delete()

            for row in rate_tables:
                SCRateTable.objects.create(
                    compensation_plan=instance,
                    **row
                )

        # Replace flat rate tables
        if flat_rate_tables is not None:
            instance.sc_flat_rate_tables.all().delete()

            for row in flat_rate_tables:
                SCFlatRateTable.objects.create(
                    compensation_plan=instance,
                    **row
                )

        if lookup_tables is not None:
            instance.sc_lookup_tables.all().delete()
            for row in lookup_tables:
                SCLookupTable.objects.create(
                    compensation_plan=instance,
                    **row,
                )

        return instance

class OrderSerializer(serializers.ModelSerializer):
    has_commission = serializers.SerializerMethodField()
    commission_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = "__all__"

    def _primary_commission(self, obj):
        sale = getattr(obj, "sale_record", None)
        if sale:
            prefetched = getattr(sale, "_prefetched_objects_cache", {})
            if "commission_set" in prefetched:
                commissions = prefetched["commission_set"]
                return commissions[0] if commissions else None
            commission = sale.commission_set.order_by("id").first()
            if commission:
                return commission
        from .models import Commission

        return (
            Commission.objects.filter(sale__order=obj).order_by("id").first()
        )

    def get_has_commission(self, obj):
        return self._primary_commission(obj) is not None

    def get_commission_amount(self, obj):
        commission = self._primary_commission(obj)
        if not commission:
            return None
        return commission.commission_amount

    def validate(self, attrs):
        from .currencies import normalize_currency
        from .field_rules import validate_order_fields

        raw = getattr(self, "initial_data", None) or {}
        if hasattr(raw, "dict"):
            raw = raw.dict()
        merged = {**raw, **attrs}
        validate_order_fields(merged, partial=self.partial)
        if "currency" in merged:
            attrs["currency"] = normalize_currency(merged.get("currency"))
        return attrs

    def validate_sales_amount(self, value):
        """
        Validate that sales_amount is non-negative and within acceptable bounds.
        """
        from decimal import Decimal
        
        # Check for negative values
        if value < 0:
            raise serializers.ValidationError(
                "Sales amount cannot be negative."
            )
        
        # Check for maximum allowed value (99,999,999.99)
        max_allowed = Decimal('99999999.99')
        if value > max_allowed:
            raise serializers.ValidationError(
                f"Sales amount cannot exceed {max_allowed}."
            )
        
        return value


class TerritorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Territory
        fields = "__all__"
        read_only_fields = ["created_at", "organization"]


class PayoutRunSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        default=None,
    )
    commission_count = serializers.SerializerMethodField()

    class Meta:
        model = PayoutRun
        fields = "__all__"
        read_only_fields = ["created_at", "paid_at", "status", "organization", "created_by"]

    def get_commission_count(self, obj):
        return obj.commissions.count()


class CommissionDisputeSerializer(serializers.ModelSerializer):
    raised_by_email = serializers.EmailField(
        source="raised_by.email",
        read_only=True,
        default=None,
    )
    resolved_by_email = serializers.EmailField(
        source="resolved_by.email",
        read_only=True,
        default=None,
    )
    employee_name = serializers.CharField(
        source="commission.employee.name",
        read_only=True,
    )
    employee_id = serializers.SerializerMethodField()
    order_id = serializers.SerializerMethodField()
    order_date = serializers.SerializerMethodField()
    commission_amount = serializers.DecimalField(
        source="commission.commission_amount",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    employee_acknowledged_by_email = serializers.EmailField(
        source="employee_acknowledged_by.email",
        read_only=True,
        default=None,
    )
    can_acknowledge = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = CommissionDispute
        fields = "__all__"
        read_only_fields = [
            "raised_by",
            "status",
            "resolved_by",
            "resolved_at",
            "employee_acknowledged_at",
            "employee_acknowledged_by",
            "created_at",
        ]

    def get_can_acknowledge(self, obj):
        from .enterprise_views import _dispute_can_acknowledge

        request = self.context.get("request")
        if not request:
            return False
        return _dispute_can_acknowledge(obj, request)

    def get_can_delete(self, obj):
        from .enterprise_views import _dispute_can_delete

        request = self.context.get("request")
        if not request:
            return False
        return _dispute_can_delete(obj, request)

    def _order_for_commission(self, obj):
        comm = obj.commission
        if not comm or not comm.sale_id:
            return None
        return getattr(comm.sale, "order", None)

    def get_order_id(self, obj):
        order = self._order_for_commission(obj)
        return order.order_id if order else None

    def get_order_date(self, obj):
        order = self._order_for_commission(obj)
        return order.order_date if order else None

    def get_employee_id(self, obj):
        order = self._order_for_commission(obj)
        if order and order.employee_id:
            return order.employee_id
        try:
            from .models import UserProfile

            profile = UserProfile.objects.filter(
                email=obj.commission.employee.email
            ).first()
            return profile.employee_id if profile else None
        except Exception:
            return None


class ExternalIntegrationSerializer(serializers.ModelSerializer):
    webhook_urls = serializers.SerializerMethodField()

    class Meta:
        model = ExternalIntegration
        fields = "__all__"
        read_only_fields = [
            "organization",
            "created_by",
            "webhook_secret",
            "last_user_sync_at",
            "last_order_sync_at",
            "created_at",
            "updated_at",
        ]

    def get_webhook_urls(self, obj):
        request = self.context.get("request")
        if not request or obj.provider != ExternalIntegration.PROVIDER_WEBHOOK:
            return {}
        if not obj.webhook_secret:
            return {}
        base = request.build_absolute_uri("/api/integrations/webhook/").rstrip("/")
        secret = obj.webhook_secret
        return {
            "users": f"{base}/{secret}/users/",
            "orders": f"{base}/{secret}/orders/",
        }


class IntegrationSyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSyncLog
        fields = "__all__"