from rest_framework import serializers
from .models import Employee, Commission, UserProfile, HierarchyRelationship, CompensationTier, Order

from .models import (
    CompensationPlan,
    SCRateTable,
    SCFlatRateTable,
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

    class Meta:
        model = Commission
        fields = '__all__'
        read_only_fields = [
            'calculated_at',
            'approved_at',
            'approved_by',
            'compensation_plan',
            'status',
        ]

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

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'

    def validate(self, attrs):
        from .field_rules import validate_user_profile_fields

        raw = getattr(self, "initial_data", None) or {}
        if hasattr(raw, "dict"):
            raw = raw.dict()
        merged = {**raw, **attrs}
        validate_user_profile_fields(merged, partial=self.partial)
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

    class Meta:
        model = CompensationPlan
        fields = '__all__'
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "effective_end_date": {"required": False, "allow_null": True},
            "position_name": {"required": False, "allow_blank": True, "allow_null": True},
            "title": {"required": False, "allow_blank": True, "allow_null": True},
            "business_group": {"required": False, "allow_blank": True, "allow_null": True},
            "pay_period_type": {"required": False},
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

        return instance

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = "__all__"

    def validate(self, attrs):
        from .field_rules import validate_order_fields

        raw = getattr(self, "initial_data", None) or {}
        if hasattr(raw, "dict"):
            raw = raw.dict()
        merged = {**raw, **attrs}
        validate_order_fields(merged, partial=self.partial)
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