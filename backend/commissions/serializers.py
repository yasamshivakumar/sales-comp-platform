from django.db import transaction
from rest_framework import serializers
from .models import Employee, Commission, UserProfile, HierarchyRelationship, CompensationTier, Order

from .models import (
    CommissionPlanVersion,
    CompensationPlan,
    PlanVersionQuota,
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


def _request_organization(serializer):
    request = serializer.context.get("request") if hasattr(serializer, "context") else None
    return getattr(request, "organization", None)


def _validate_tenant_owned(obj, organization, field_name):
    if obj is None or organization is None:
        return
    obj_org_id = getattr(obj, "organization_id", None)
    if obj_org_id and obj_org_id != organization.id:
        raise serializers.ValidationError(
            {field_name: "Selected value does not belong to this organization."}
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
    plan_version_number = serializers.IntegerField(
        source='plan_version.version_number',
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
            'plan_version',
            'status',
        ]

    def get_has_open_dispute(self, obj):
        return obj.disputes.filter(status=CommissionDispute.STATUS_OPEN).exists()

    def get_order_id(self, obj):
        order = getattr(obj.sale, 'order', None) if obj.sale_id else None
        if not order and getattr(obj, "calculation_scope", "") == Commission.SCOPE_EMPLOYEE_MONTH:
            return "Monthly summary"
        return order.order_id if order else None

    def get_order_date(self, obj):
        order = getattr(obj.sale, 'order', None) if obj.sale_id else None
        if not order and getattr(obj, "period_start", None):
            return obj.period_start
        return order.order_date if order else None

    def get_employee_id(self, obj):
        order = getattr(obj.sale, "order", None) if obj.sale_id else None
        if order and order.employee_id:
            return order.employee_id
        from .tenants import allow_default_organization_fallback

        qs = UserProfile.objects.filter(email__iexact=obj.employee.email)
        org_id = getattr(obj, "organization_id", None) or getattr(order, "organization_id", None)
        if org_id:
            profile = qs.filter(organization_id=org_id).first()
            if not profile and allow_default_organization_fallback():
                profile = qs.filter(organization__isnull=True).first()
        else:
            profile = qs.first()
        if profile:
            return profile.employee_id
        return obj.employee.email.split("@")[0]

    def get_currency(self, obj):
        from .business_groups import currency_for_business_group
        from .currencies import normalize_currency

        plan = getattr(obj, "compensation_plan", None)
        if plan and str(plan.business_group or "").strip():
            return currency_for_business_group(plan.business_group)

        order = getattr(obj.sale, "order", None) if obj.sale_id else None
        if order:
            from .services import derive_order_currency

            return derive_order_currency(order)

        stored = normalize_currency(getattr(obj, "currency", None), default="")
        if stored:
            return stored
        return normalize_currency(getattr(order, "currency", None) if order else None)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'

    def validate(self, attrs):
        from .currencies import normalize_currency
        from .field_rules import validate_user_profile_fields

        org = _request_organization(self)
        _validate_tenant_owned(attrs.get("territory"), org, "territory")
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
        read_only_fields = ['compensation_plan', 'plan_version']


# ------------------------------------------
# SC Flat Rate Table Serializer
# ------------------------------------------
class SCFlatRateTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCFlatRateTable
        fields = '__all__'
        read_only_fields = ['compensation_plan', 'plan_version']


class SCLookupTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SCLookupTable
        fields = '__all__'
        read_only_fields = ['compensation_plan', 'plan_version']


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

    def validate(self, attrs):
        version = attrs.get("plan_version") or getattr(self.instance, "plan_version", None)
        if version is not None and version.status != CommissionPlanVersion.STATUS_DRAFT:
            raise serializers.ValidationError(
                f"Cannot modify rules on {version.status} version "
                f"{version.version_number}. Clone the version to edit."
            )
        return attrs

    def _sync_children(self, rule, conditions=None, results=None):
        if conditions is not None:
            rule.conditions.all().delete()
            for row in conditions:
                CommissionRuleCondition.objects.create(rule=rule, **row)
        if results is not None:
            rule.results.all().delete()
            for row in results:
                CommissionRuleResult.objects.create(rule=rule, **row)

    @transaction.atomic
    def create(self, validated_data):
        conditions = validated_data.pop("conditions", [])
        results = validated_data.pop("results", [])
        rule = CommissionRule.objects.create(**validated_data)
        self._sync_children(rule, conditions, results)
        return rule

    @transaction.atomic
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
# Commission Plan Version Serializers
# ------------------------------------------
class PlanVersionQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersionQuota
        fields = "__all__"
        read_only_fields = ["plan_version", "created_at", "updated_at"]


class CommissionPlanVersionSerializer(serializers.ModelSerializer):
    sc_rate_tables = SCRateTableSerializer(many=True, required=False)
    sc_flat_rate_tables = SCFlatRateTableSerializer(many=True, required=False)
    sc_lookup_tables = SCLookupTableSerializer(many=True, required=False)
    commission_rules = CommissionRuleSerializer(many=True, read_only=True)
    quotas = PlanVersionQuotaSerializer(many=True, required=False)
    plan_name = serializers.CharField(
        source="compensation_plan.plan_name", read_only=True
    )
    published_by_email = serializers.EmailField(
        source="published_by.email", read_only=True, default=None
    )
    created_from_version_number = serializers.IntegerField(
        source="created_from_version.version_number", read_only=True, default=None
    )
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = CommissionPlanVersion
        fields = "__all__"
        read_only_fields = [
            "organization",
            "compensation_plan",
            "version_number",
            "status",
            "published_at",
            "published_by",
            "created_from_version",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is not None and not instance.is_editable:
            # Quota updates are allowed on non-archived versions (quotas are
            # period data, not plan logic); everything else is immutable.
            non_quota_changes = {k: v for k, v in attrs.items() if k != "quotas"}
            if non_quota_changes:
                raise serializers.ValidationError(
                    f"Version {instance.version_number} is {instance.status} and "
                    "immutable. Clone it to create an editable draft."
                )
            if instance.status == CommissionPlanVersion.STATUS_ARCHIVED:
                raise serializers.ValidationError(
                    "Archived versions are read-only, including quotas."
                )
        effective_from = attrs.get(
            "effective_from", getattr(instance, "effective_from", None)
        )
        effective_to = attrs.get(
            "effective_to", getattr(instance, "effective_to", None)
        )
        if effective_from and effective_to and effective_to < effective_from:
            raise serializers.ValidationError(
                {"effective_to": "effective_to cannot be before effective_from."}
            )
        return attrs

    def _sync_version_tables(
        self, version, rate_tables=None, flat_rate_tables=None, lookup_tables=None
    ):
        plan = version.compensation_plan
        if rate_tables is not None:
            version.sc_rate_tables.all().delete()
            for row in rate_tables:
                SCRateTable.objects.create(
                    compensation_plan=plan, plan_version=version, **row
                )
        if flat_rate_tables is not None:
            version.sc_flat_rate_tables.all().delete()
            for row in flat_rate_tables:
                SCFlatRateTable.objects.create(
                    compensation_plan=plan, plan_version=version, **row
                )
        if lookup_tables is not None:
            version.sc_lookup_tables.all().delete()
            for row in lookup_tables:
                SCLookupTable.objects.create(
                    compensation_plan=plan, plan_version=version, **row
                )

    def _sync_quotas(self, version, quotas):
        version.quotas.all().delete()
        for row in quotas:
            PlanVersionQuota.objects.create(plan_version=version, **row)

    @transaction.atomic
    def update(self, instance, validated_data):
        rate_tables = validated_data.pop("sc_rate_tables", None)
        flat_rate_tables = validated_data.pop("sc_flat_rate_tables", None)
        lookup_tables = validated_data.pop("sc_lookup_tables", None)
        quotas = validated_data.pop("quotas", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if instance.is_editable:
            self._sync_version_tables(
                instance, rate_tables, flat_rate_tables, lookup_tables
            )
        if quotas is not None:
            self._sync_quotas(instance, quotas)
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
        try:
            merged = normalize_compensation_plan_payload({**raw, **attrs})
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        validate_compensation_plan_fields(merged, partial=self.partial)
        org = _request_organization(self)
        _validate_tenant_owned(attrs.get("territory"), org, "territory")

        # Drop UI-only aliases before model create/update.
        merged.pop("comp_period", None)
        merged.pop("plan_month", None)
        merged.pop("table_type", None)

        return merged

    # Header fields that may change without editing version content
    # (operational metadata, not calculation logic).
    _NON_VERSIONED_FIELDS = {
        "plan_name",
        "description",
        "status",
        "plan_type",
        "owner",
        "approver",
        "last_modified_by",
    }

    def _display_version(self, plan):
        from .plan_versions import display_version_for_plan

        return display_version_for_plan(plan)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        version = self._display_version(instance)

        if version is not None:
            # Scope nested collections to the display version so cloned
            # versions never leak rows into the legacy plan payload.
            data["sc_rate_tables"] = SCRateTableSerializer(
                version.sc_rate_tables.all(), many=True
            ).data
            data["sc_flat_rate_tables"] = SCFlatRateTableSerializer(
                version.sc_flat_rate_tables.all(), many=True
            ).data
            data["sc_lookup_tables"] = SCLookupTableSerializer(
                version.sc_lookup_tables.all(), many=True
            ).data
            data["commission_rules"] = CommissionRuleSerializer(
                version.commission_rules.all(), many=True
            ).data

        versions = list(instance.versions.all())
        data["versions_count"] = len(versions)
        data["current_version"] = (
            {
                "id": version.id,
                "version_number": version.version_number,
                "status": version.status,
                "effective_from": str(version.effective_from)
                if version.effective_from
                else None,
                "effective_to": str(version.effective_to)
                if version.effective_to
                else None,
                "is_editable": version.is_editable,
            }
            if version is not None
            else None
        )

        from .plan_catalog import enrich_plan_enterprise_fields

        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        skip_participants = False
        lite = False
        if request is not None:
            skip_participants = str(
                request.query_params.get("skip_participant_count") or ""
            ).lower() in ("1", "true", "yes")
            lite = str(request.query_params.get("lite") or "").lower() in (
                "1",
                "true",
                "yes",
            )

        # Coverage aggregates help catalog cards answer "who is covered?"
        # Pass lite=1 to skip for very large tenant scans.
        include_coverage = not lite

        if skip_participants:
            enterprise = enrich_plan_enterprise_fields(
                instance,
                version,
                organization=org,
                participant_count=0,
                include_coverage=False,
            )
            enterprise["participant_count"] = None
        else:
            enterprise = enrich_plan_enterprise_fields(
                instance,
                version,
                organization=org,
                include_coverage=include_coverage,
            )
        data.update(enterprise)
        return data

    def _sync_tables(self, plan, rate_tables=None, flat_rate_tables=None,
                     lookup_tables=None, version=None):
        def _clean(row):
            row = dict(row)
            row.pop("plan_version", None)
            return row

        if rate_tables is not None:
            (version.sc_rate_tables if version else plan.sc_rate_tables).all().delete()
            for row in rate_tables:
                SCRateTable.objects.create(
                    compensation_plan=plan, plan_version=version, **_clean(row)
                )
        if flat_rate_tables is not None:
            (
                version.sc_flat_rate_tables if version else plan.sc_flat_rate_tables
            ).all().delete()
            for row in flat_rate_tables:
                SCFlatRateTable.objects.create(
                    compensation_plan=plan, plan_version=version, **_clean(row)
                )
        if lookup_tables is not None:
            (
                version.sc_lookup_tables if version else plan.sc_lookup_tables
            ).all().delete()
            for row in lookup_tables:
                SCLookupTable.objects.create(
                    compensation_plan=plan, plan_version=version, **_clean(row)
                )

    def _mirror_plan_to_version(self, plan, version):
        from .plan_versions import VERSION_SNAPSHOT_FIELDS

        for field in VERSION_SNAPSHOT_FIELDS:
            setattr(version, field, getattr(plan, field))
        version.effective_from = plan.effective_start_date
        version.effective_to = plan.effective_end_date
        version.save()

    def _request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None) if request else None

    @transaction.atomic
    def create(self, validated_data):
        from .plan_versions import (
            _has_rate_configuration,
            create_initial_version,
            publish_version,
        )

        rate_tables = validated_data.pop("sc_rate_tables", [])
        flat_rate_tables = validated_data.pop("sc_flat_rate_tables", [])
        lookup_tables = validated_data.pop("sc_lookup_tables", [])
        user = self._request_user()
        if user and getattr(user, "is_authenticated", False):
            validated_data["last_modified_by"] = user
        plan = CompensationPlan.objects.create(**validated_data)

        version = create_initial_version(plan)
        self._sync_tables(
            plan, rate_tables, flat_rate_tables, lookup_tables, version=version
        )

        # Legacy flow auto-publishes Active plans, but only once rate rows
        # exist. Publishing an empty version would block calculations (the
        # engine only uses Published versions) while later rate edits land
        # on a new draft — leaving the plan silently unable to pay.
        if plan.status == "Active" and _has_rate_configuration(version):
            publish_version(version, user=self._request_user())

        return plan

    @transaction.atomic
    def update(self, instance, validated_data):
        rate_tables = validated_data.pop("sc_rate_tables", None)
        flat_rate_tables = validated_data.pop("sc_flat_rate_tables", None)
        lookup_tables = validated_data.pop("sc_lookup_tables", None)

        version = self._display_version(instance)
        has_table_changes = any(
            tables is not None
            for tables in (rate_tables, flat_rate_tables, lookup_tables)
        )
        versioned_field_changes = {
            attr: value
            for attr, value in validated_data.items()
            if attr not in self._NON_VERSIONED_FIELDS
            and getattr(instance, attr) != value
        }

        if (
            version is not None
            and not version.is_editable
            and (has_table_changes or versioned_field_changes)
        ):
            raise serializers.ValidationError(
                f"Version {version.version_number} of this plan is "
                f"{version.status} and immutable. Clone it to create an "
                "editable draft, make changes there, then publish."
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        user = self._request_user()
        if user and getattr(user, "is_authenticated", False):
            instance.last_modified_by = user
        instance.save()

        if version is not None and version.is_editable:
            self._sync_tables(
                instance, rate_tables, flat_rate_tables, lookup_tables,
                version=version,
            )
            self._mirror_plan_to_version(instance, version)
            self._maybe_autopublish_initial_version(instance, version)
        elif version is None:
            # Pre-versioning plans (legacy data) keep the old behavior.
            self._sync_tables(instance, rate_tables, flat_rate_tables, lookup_tables)
        return instance

    def _maybe_autopublish_initial_version(self, plan, version):
        """Complete the legacy setup flow: a plan is created Active first and
        rate rows are added afterwards. Once the first rates land on the
        initial draft — and no version has ever been published — publish it so
        calculations start working without requiring the version UI."""
        from .models import CommissionPlanVersion
        from .plan_versions import _has_rate_configuration, publish_version

        if plan.status != "Active":
            return
        if not _has_rate_configuration(version):
            return
        has_published = CommissionPlanVersion.objects.filter(
            compensation_plan=plan,
            status=CommissionPlanVersion.STATUS_PUBLISHED,
        ).exists()
        if has_published:
            return
        publish_version(version, user=self._request_user())

class OrderSerializer(serializers.ModelSerializer):
    has_commission = serializers.SerializerMethodField()
    commission_amount = serializers.SerializerMethodField()
    commission_skip_reason = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = "__all__"

    def _primary_commission(self, obj):
        from .transaction_ops import resolve_primary_commission

        return resolve_primary_commission(obj)

    def get_has_commission(self, obj):
        return self._primary_commission(obj) is not None

    def get_commission_amount(self, obj):
        commission = self._primary_commission(obj)
        if not commission:
            return None
        return commission.commission_amount

    def get_commission_skip_reason(self, obj):
        if self.get_has_commission(obj):
            return None
        from .imports import commission_skip_reason

        return commission_skip_reason(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from .services import derive_order_currency
        from .transaction_ops import enrich_order_transaction_fields

        data["currency"] = derive_order_currency(instance)
        commission = self._primary_commission(instance)
        data.update(enrich_order_transaction_fields(instance, commission))
        if self.context.get("include_workspace"):
            from .transaction_ops import (
                build_order_commission_breakdown,
                build_order_history,
            )

            data["commission_breakdown"] = build_order_commission_breakdown(
                instance, commission
            )
            data["audit_history"] = build_order_history(instance)
        return data

    def validate(self, attrs):
        from .currencies import normalize_currency
        from .field_rules import validate_order_fields
        from .services import _profile_for_employee, normalize_order_region_fields

        org = _request_organization(self)
        _validate_tenant_owned(attrs.get("territory"), org, "territory")
        raw = getattr(self, "initial_data", None) or {}
        if hasattr(raw, "dict"):
            raw = raw.dict()
        merged = {**raw, **attrs}
        instance = getattr(self, "instance", None)
        if instance:
            for field in ("business_group", "currency", "employee_id", "order_date", "position_name"):
                if field not in merged or merged.get(field) in (None, ""):
                    merged[field] = getattr(instance, field, None)
        validate_order_fields(merged, partial=self.partial)
        profile = _profile_for_employee(merged.get("employee_id"), org)
        merged = normalize_order_region_fields(merged, profile=profile)
        if merged.get("currency"):
            attrs["currency"] = normalize_currency(merged.get("currency"))
        if merged.get("business_group"):
            attrs["business_group"] = merged.get("business_group")
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
    currency = serializers.SerializerMethodField()
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

    def validate(self, attrs):
        org = _request_organization(self)
        _validate_tenant_owned(attrs.get("commission"), org, "commission")
        return attrs

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

    def get_currency(self, obj):
        from .currencies import normalize_currency

        order = self._order_for_commission(obj)
        return normalize_currency(getattr(order, "currency", None))

    def get_employee_id(self, obj):
        order = self._order_for_commission(obj)
        if order and order.employee_id:
            return order.employee_id
        from .models import UserProfile

        employee = getattr(getattr(obj, "commission", None), "employee", None)
        employee_email = getattr(employee, "email", None)
        if not employee_email:
            return None
        profile = UserProfile.objects.filter(
            email__iexact=employee_email,
            organization=getattr(obj.commission, "organization", None),
        ).first()
        return profile.employee_id if profile else None


def _mask_integration_credentials(credentials):
    from .credential_crypto import mask_credentials

    return mask_credentials(credentials)


class ExternalIntegrationSerializer(serializers.ModelSerializer):
    webhook_urls = serializers.SerializerMethodField()
    credentials_masked = serializers.SerializerMethodField()
    credentials = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = ExternalIntegration
        exclude = ["encrypted_credentials"]
        read_only_fields = [
            "organization",
            "created_by",
            "webhook_secret",
            "last_user_sync_at",
            "last_order_sync_at",
            "last_auto_sync_at",
            "last_sync_at",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Never expose raw or ciphertext secrets over the API.
        data.pop("credentials", None)
        data.pop("encrypted_credentials", None)
        return data

    def get_credentials_masked(self, obj):
        try:
            return _mask_integration_credentials(obj.get_decrypted_credentials())
        except Exception:
            return _mask_integration_credentials(getattr(obj, "credentials", None))

    def get_webhook_urls(self, obj):
        request = self.context.get("request")
        if not request or not obj.webhook_secret:
            return {}
        if obj.provider == ExternalIntegration.PROVIDER_WEBHOOK:
            base = request.build_absolute_uri("/api/integrations/webhook/").rstrip("/")
            secret = obj.webhook_secret
            return {
                "users": f"{base}/{secret}/users/",
                "orders": f"{base}/{secret}/orders/",
            }
        if obj.provider == ExternalIntegration.PROVIDER_HUBSPOT:
            base = request.build_absolute_uri("/api/integrations/hubspot/webhook/").rstrip(
                "/"
            )
            return {"events": f"{base}/{obj.webhook_secret}/"}
        return {}

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", None) or {}
        instance = super().create(validated_data)
        if credentials:
            instance.set_encrypted_credentials(credentials)
            instance.save(
                update_fields=["credentials", "encrypted_credentials", "updated_at"]
            )
        return instance

    def update(self, instance, validated_data):
        credentials = validated_data.pop("credentials", serializers.empty)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if credentials is not serializers.empty and credentials is not None:
            merged = dict(instance.get_decrypted_credentials() or {})
            for key, value in credentials.items():
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                if value == "••••••••":
                    continue
                merged[key] = value
            instance.set_encrypted_credentials(merged)
        instance.save()
        return instance


class IntegrationSyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSyncLog
        fields = "__all__"