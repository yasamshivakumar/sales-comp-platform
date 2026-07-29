"""Commission plan version lifecycle: draft -> published (immutable) -> archived.

Enterprise behavior:
- One logical CompensationPlan, many effective-dated CommissionPlanVersion rows.
- Published versions are immutable; to change a plan, clone -> edit draft -> publish.
- The calculation engine only ever uses Published versions.
"""
import logging
from datetime import date, timedelta

from django.db import models, transaction
from django.utils import timezone

from .models import (
    CommissionPlanVersion,
    CompensationPlan,
    CommissionRule,
    CommissionRuleCondition,
    CommissionRuleResult,
    PlanVersionQuota,
    SCFlatRateTable,
    SCLookupTable,
    SCRateTable,
)

logger = logging.getLogger("commissions")

VERSION_SNAPSHOT_FIELDS = [
    "pay_period_type",
    "plan_basis",
    "commission_table_type",
    "tier_calculation_method",
    "position_name",
    "role",
    "territory",
    "title",
    "business_group",
]


class PlanVersionError(Exception):
    """Raised for invalid plan-version transitions; views translate to 4xx."""


def ensure_editable(version):
    if version.status != CommissionPlanVersion.STATUS_DRAFT:
        raise PlanVersionError(
            f"Version {version.version_number} is {version.status} and immutable. "
            "Clone it to create an editable draft."
        )


def _ranges_overlap(a_from, a_to, b_from, b_to):
    a_end = a_to or date.max
    b_end = b_to or date.max
    return a_from <= b_end and b_from <= a_end


def validate_no_published_overlap(version):
    """Only one Published version may be effective for any given date."""
    if not version.effective_from:
        raise PlanVersionError("effective_from is required to publish a version.")
    if version.effective_to and version.effective_to < version.effective_from:
        raise PlanVersionError("effective_to cannot be before effective_from.")

    siblings = CommissionPlanVersion.objects.filter(
        compensation_plan=version.compensation_plan,
        status=CommissionPlanVersion.STATUS_PUBLISHED,
    ).exclude(pk=version.pk)

    for other in siblings:
        if _ranges_overlap(
            version.effective_from,
            version.effective_to,
            other.effective_from,
            other.effective_to,
        ):
            raise PlanVersionError(
                f"Effective dates overlap Published version {other.version_number} "
                f"({other.effective_from} – {other.effective_to or 'open-ended'}). "
                "Adjust the effective range or archive the other version."
            )


def supersede_overlapping_published(version):
    """Auto-retire Published versions the new version replaces (enterprise
    'publish supersedes' behavior — no manual archive step required).

    - A sibling that started before the new version keeps its history: its
      effective_to is trimmed to the day before the new version starts.
    - A sibling fully inside the new version's range is archived.

    Returns a list of {version_number, action} dicts for auditing.
    """
    if not version.effective_from:
        raise PlanVersionError("effective_from is required to publish a version.")
    if version.effective_to and version.effective_to < version.effective_from:
        raise PlanVersionError("effective_to cannot be before effective_from.")

    actions = []
    siblings = CommissionPlanVersion.objects.filter(
        compensation_plan=version.compensation_plan,
        status=CommissionPlanVersion.STATUS_PUBLISHED,
    ).exclude(pk=version.pk)

    for other in siblings:
        if not _ranges_overlap(
            version.effective_from,
            version.effective_to,
            other.effective_from,
            other.effective_to,
        ):
            continue

        if other.effective_from < version.effective_from:
            # Keep the sibling for its historical window; end-date it just
            # before the new version takes over.
            other.effective_to = version.effective_from - timedelta(days=1)
            other.save(update_fields=["effective_to", "updated_at"])
            actions.append(
                {
                    "version_number": other.version_number,
                    "action": "end_dated",
                    "effective_to": str(other.effective_to),
                }
            )
            logger.info(
                "Publish supersede: v%s of plan %s end-dated to %s (replaced by v%s)",
                other.version_number,
                version.compensation_plan_id,
                other.effective_to,
                version.version_number,
            )
        else:
            # The new version covers this sibling from its start — archive it.
            other.status = CommissionPlanVersion.STATUS_ARCHIVED
            other.save(update_fields=["status", "updated_at"])
            actions.append(
                {"version_number": other.version_number, "action": "archived"}
            )
            logger.info(
                "Publish supersede: v%s of plan %s archived (replaced by v%s)",
                other.version_number,
                version.compensation_plan_id,
                version.version_number,
            )

    return actions


def _has_rate_configuration(version):
    table_type = version.commission_table_type
    if table_type in ("RATE", "HIGHEST", "MARGINAL"):
        return version.sc_rate_tables.filter(is_active=True).exists()
    if table_type == "FLAT":
        return version.sc_flat_rate_tables.filter(is_active=True).exists()
    if table_type == "LOOKUP":
        return version.sc_lookup_tables.filter(is_active=True).exists()
    return True


def next_version_number(plan):
    latest = (
        CommissionPlanVersion.objects.filter(compensation_plan=plan)
        .aggregate(models.Max("version_number"))["version_number__max"]
    )
    return (latest or 0) + 1


def create_initial_version(plan, status=CommissionPlanVersion.STATUS_DRAFT):
    """Version 1 for a newly created plan; snapshots the plan header config."""
    return CommissionPlanVersion.objects.create(
        organization_id=plan.organization_id,
        compensation_plan=plan,
        version_number=next_version_number(plan),
        status=status,
        effective_from=plan.effective_start_date,
        effective_to=plan.effective_end_date,
        pay_period_type=plan.pay_period_type,
        plan_basis=plan.plan_basis,
        commission_table_type=plan.commission_table_type,
        tier_calculation_method=plan.tier_calculation_method,
        position_name=plan.position_name,
        role=plan.role,
        territory_id=plan.territory_id,
        title=plan.title,
        business_group=plan.business_group,
    )


def copy_version_children(source, target):
    """Deep-copy rate tables, lookup rows, rules (with conditions/results),
    and monthly quotas from one version to another."""
    plan = target.compensation_plan

    for row in source.sc_rate_tables.all():
        SCRateTable.objects.create(
            compensation_plan=plan,
            plan_version=target,
            tier_name=row.tier_name,
            from_amount=row.from_amount,
            to_amount=row.to_amount,
            commission_rate=row.commission_rate,
            bonus_amount=row.bonus_amount,
            sequence=row.sequence,
            is_active=row.is_active,
        )

    for row in source.sc_flat_rate_tables.all():
        SCFlatRateTable.objects.create(
            compensation_plan=plan,
            plan_version=target,
            flat_rate=row.flat_rate,
            bonus_amount=row.bonus_amount,
            minimum_sales_threshold=row.minimum_sales_threshold,
            is_active=row.is_active,
        )

    for row in source.sc_lookup_tables.all():
        SCLookupTable.objects.create(
            compensation_plan=plan,
            plan_version=target,
            tier_name=row.tier_name,
            product_name=row.product_name,
            service_name=row.service_name,
            distribution=row.distribution,
            from_amount=row.from_amount,
            to_amount=row.to_amount,
            commission_rate=row.commission_rate,
            bonus_amount=row.bonus_amount,
            sequence=row.sequence,
            is_active=row.is_active,
        )

    for rule in source.commission_rules.prefetch_related(
        "conditions", "results", "employee_assignments"
    ):
        new_rule = CommissionRule.objects.create(
            organization_id=rule.organization_id,
            compensation_plan=plan,
            plan_version=target,
            name=rule.name,
            description=rule.description,
            rule_type=rule.rule_type,
            multiplier=rule.multiplier,
            tags=rule.tags,
            version_label=rule.version_label,
            effective_start_date=rule.effective_start_date,
            effective_end_date=rule.effective_end_date,
            active_start_date=rule.active_start_date,
            active_end_date=rule.active_end_date,
            scope=getattr(rule, "scope", CommissionRule.SCOPE_PLAN_DEFAULT),
            priority=getattr(rule, "priority", 5),
            condition_logic=getattr(rule, "condition_logic", CommissionRule.LOGIC_AND),
            sequence=rule.sequence,
            is_active=rule.is_active,
            stop_on_match=rule.stop_on_match,
        )
        for condition in rule.conditions.all():
            CommissionRuleCondition.objects.create(
                rule=new_rule,
                field=condition.field,
                operator=condition.operator,
                value=condition.value,
                sequence=condition.sequence,
                is_active=condition.is_active,
            )
        for result in rule.results.all():
            fields = {
                field.name: getattr(result, field.name)
                for field in CommissionRuleResult._meta.concrete_fields
                if field.name not in ("id", "rule")
            }
            CommissionRuleResult.objects.create(rule=new_rule, **fields)
        from .models import EmployeeCommissionRuleAssignment

        EmployeeCommissionRuleAssignment.objects.bulk_create(
            [
                EmployeeCommissionRuleAssignment(
                    organization_id=row.organization_id,
                    employee_id=row.employee_id,
                    rule=new_rule,
                    assigned_by_id=row.assigned_by_id,
                )
                for row in rule.employee_assignments.all()
            ],
            ignore_conflicts=True,
        )

    for quota in source.quotas.all():
        PlanVersionQuota.objects.create(
            plan_version=target,
            year=quota.year,
            month=quota.month,
            quota_amount=quota.quota_amount,
            currency=quota.currency,
        )


@transaction.atomic
def clone_version(version, user=None, description=""):
    """Deep-copy a version into a new Draft (next version number)."""
    plan = CompensationPlan.objects.select_for_update().get(
        pk=version.compensation_plan_id
    )

    existing_draft = CommissionPlanVersion.objects.filter(
        compensation_plan=plan,
        status=CommissionPlanVersion.STATUS_DRAFT,
    ).first()
    if existing_draft:
        raise PlanVersionError(
            f"A draft (version {existing_draft.version_number}) already exists for "
            "this plan. Edit or publish it before cloning again."
        )

    draft = CommissionPlanVersion.objects.create(
        organization_id=plan.organization_id,
        compensation_plan=plan,
        version_number=next_version_number(plan),
        status=CommissionPlanVersion.STATUS_DRAFT,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        created_from_version=version,
        description=description or f"Cloned from version {version.version_number}",
        pay_period_type=version.pay_period_type,
        plan_basis=version.plan_basis,
        commission_table_type=version.commission_table_type,
        tier_calculation_method=version.tier_calculation_method,
        position_name=version.position_name,
        role=version.role,
        territory_id=version.territory_id,
        title=version.title,
        business_group=version.business_group,
    )
    copy_version_children(version, draft)
    logger.info(
        "Cloned plan version %s v%s -> v%s (plan_id=%s)",
        plan.plan_name,
        version.version_number,
        draft.version_number,
        plan.pk,
    )
    return draft


@transaction.atomic
def publish_version(version, user=None, strict=True):
    """Draft -> Published (immutable). Strict mode requires rate configuration.

    Publishing supersedes: overlapping Published versions are automatically
    end-dated (if they started earlier) or archived (if fully replaced), so
    admins never have to manually archive before publishing.
    """
    plan = CompensationPlan.objects.select_for_update().get(
        pk=version.compensation_plan_id
    )
    version = CommissionPlanVersion.objects.select_for_update().get(pk=version.pk)

    if version.status == CommissionPlanVersion.STATUS_PUBLISHED:
        return version
    if version.status == CommissionPlanVersion.STATUS_ARCHIVED:
        raise PlanVersionError(
            "Archived versions cannot be published. Clone into a new draft instead."
        )

    if strict and not _has_rate_configuration(version):
        raise PlanVersionError(
            "Cannot publish: configure at least one active rate row for the "
            f"{version.commission_table_type} table type."
        )

    superseded = supersede_overlapping_published(version)
    # Safety net: after superseding there must be no remaining overlap.
    validate_no_published_overlap(version)

    version.status = CommissionPlanVersion.STATUS_PUBLISHED
    version.published_at = timezone.now()
    if user is not None and getattr(user, "is_authenticated", False):
        version.published_by = user
    version.save(
        update_fields=["status", "published_at", "published_by", "updated_at"]
    )

    _mirror_version_to_plan(plan, version)
    logger.info(
        "Published plan version %s v%s (plan_id=%s)%s",
        plan.plan_name,
        version.version_number,
        plan.pk,
        f" superseding {superseded}" if superseded else "",
    )
    version.superseded_versions = superseded
    return version


@transaction.atomic
def archive_version(version, user=None):
    """Published/Draft -> Archived. Archived versions stay readable forever."""
    plan = CompensationPlan.objects.select_for_update().get(
        pk=version.compensation_plan_id
    )
    version = CommissionPlanVersion.objects.select_for_update().get(pk=version.pk)

    if version.status == CommissionPlanVersion.STATUS_ARCHIVED:
        return version

    version.status = CommissionPlanVersion.STATUS_ARCHIVED
    version.save(update_fields=["status", "updated_at"])

    has_published = CommissionPlanVersion.objects.filter(
        compensation_plan=plan,
        status=CommissionPlanVersion.STATUS_PUBLISHED,
    ).exists()
    if not has_published and plan.status == "Active":
        plan.status = "Inactive"
        plan.save(update_fields=["status", "updated_at"])
    return version


def delete_version(version):
    """Only never-published drafts may be deleted."""
    ensure_editable(version)
    version.delete()


def _mirror_version_to_plan(plan, version):
    """Keep legacy plan header fields in sync with the newest published
    version so existing list/detail consumers stay accurate."""
    plan.status = "Active"
    plan.effective_start_date = version.effective_from
    plan.effective_end_date = version.effective_to
    plan.pay_period_type = version.pay_period_type
    plan.plan_basis = version.plan_basis
    plan.commission_table_type = version.commission_table_type
    plan.tier_calculation_method = version.tier_calculation_method
    plan.position_name = version.position_name
    plan.role = version.role
    plan.territory_id = version.territory_id
    plan.title = version.title
    plan.business_group = version.business_group
    plan.save()


def display_version_for_plan(plan):
    """Version shown/edited by legacy plan endpoints: the draft when one
    exists, else the most recent published, else the latest version."""
    versions = list(plan.versions.all())
    if not versions:
        return None
    drafts = [v for v in versions if v.status == CommissionPlanVersion.STATUS_DRAFT]
    if drafts:
        return drafts[0]
    published = [
        v for v in versions if v.status == CommissionPlanVersion.STATUS_PUBLISHED
    ]
    if published:
        return max(published, key=lambda v: v.version_number)
    return max(versions, key=lambda v: v.version_number)


def compare_versions(left, right):
    """Structured diff between two versions of the same plan."""

    def _header(version):
        return {
            "version_number": version.version_number,
            "status": version.status,
            "effective_from": str(version.effective_from),
            "effective_to": str(version.effective_to) if version.effective_to else None,
            "pay_period_type": version.pay_period_type,
            "plan_basis": version.plan_basis,
            "commission_table_type": version.commission_table_type,
            "position_name": version.position_name or "",
            "role": version.role or "",
            "business_group": version.business_group or "",
            "description": version.description or "",
        }

    def _rate_rows(version):
        return [
            {
                "tier_name": r.tier_name or "",
                "from_amount": str(r.from_amount),
                "to_amount": str(r.to_amount) if r.to_amount is not None else None,
                "commission_rate": str(r.commission_rate),
                "bonus_amount": str(r.bonus_amount),
                "sequence": r.sequence,
                "is_active": r.is_active,
            }
            for r in version.sc_rate_tables.all().order_by("sequence", "from_amount")
        ]

    def _flat_rows(version):
        return [
            {
                "flat_rate": str(r.flat_rate),
                "bonus_amount": str(r.bonus_amount),
                "minimum_sales_threshold": str(r.minimum_sales_threshold),
                "is_active": r.is_active,
            }
            for r in version.sc_flat_rate_tables.all().order_by("id")
        ]

    def _lookup_rows(version):
        return [
            {
                "tier_name": r.tier_name or "",
                "product_name": r.product_name,
                "service_name": r.service_name,
                "distribution": r.distribution,
                "from_amount": str(r.from_amount),
                "to_amount": str(r.to_amount) if r.to_amount is not None else None,
                "commission_rate": str(r.commission_rate),
                "bonus_amount": str(r.bonus_amount),
                "sequence": r.sequence,
                "is_active": r.is_active,
            }
            for r in version.sc_lookup_tables.all().order_by("sequence", "id")
        ]

    def _rules(version):
        rows = []
        for rule in version.commission_rules.prefetch_related(
            "conditions", "results"
        ).order_by("sequence", "id"):
            rows.append(
                {
                    "name": rule.name,
                    "rule_type": rule.rule_type,
                    "sequence": rule.sequence,
                    "is_active": rule.is_active,
                    "stop_on_match": rule.stop_on_match,
                    "conditions": [
                        f"{c.field} {c.operator} {c.value}"
                        for c in rule.conditions.all().order_by("sequence", "id")
                    ],
                    "results": [
                        f"{r.result_name or r.result_rate_type}: {r.rate_value}"
                        for r in rule.results.all().order_by("sequence", "id")
                    ],
                }
            )
        return rows

    def _quotas(version):
        return [
            {
                "year": q.year,
                "month": q.month,
                "quota_amount": str(q.quota_amount),
                "currency": q.currency,
            }
            for q in version.quotas.all().order_by("year", "month")
        ]

    left_header = _header(left)
    right_header = _header(right)
    header_diff = [
        {"field": key, "left": left_header[key], "right": right_header[key]}
        for key in left_header
        if key not in ("version_number", "status")
        and left_header[key] != right_header[key]
    ]

    return {
        "left": left_header,
        "right": right_header,
        "header_diff": header_diff,
        "rate_tables": {"left": _rate_rows(left), "right": _rate_rows(right)},
        "flat_rate_tables": {"left": _flat_rows(left), "right": _flat_rows(right)},
        "lookup_tables": {"left": _lookup_rows(left), "right": _lookup_rows(right)},
        "rules": {"left": _rules(left), "right": _rules(right)},
        "quotas": {"left": _quotas(left), "right": _quotas(right)},
    }
