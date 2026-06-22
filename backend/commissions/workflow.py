"""Multi-step commission approval, payouts, and dispute guards."""

import logging

from django.db.models import Q
from django.utils import timezone

from .models import Commission, CommissionDispute, PayoutRun

logger = logging.getLogger("commissions")


def _open_dispute_commission_ids():
    return CommissionDispute.objects.filter(
        status=CommissionDispute.STATUS_OPEN
    ).values_list("commission_id", flat=True)


def commission_has_open_dispute(commission):
    return commission.disputes.filter(status=CommissionDispute.STATUS_OPEN).exists()


def filter_manager_approvable(queryset):
    """Calculated commissions without open disputes."""
    return queryset.filter(status=Commission.STATUS_CALCULATED).exclude(
        id__in=_open_dispute_commission_ids()
    )


def filter_finance_approvable(queryset):
    """Manager-approved commissions without open disputes."""
    return queryset.filter(status=Commission.STATUS_MANAGER_APPROVED).exclude(
        id__in=_open_dispute_commission_ids()
    )


def approve_manager_commissions(queryset, approved_by_user):
    now = timezone.now()
    qs = filter_manager_approvable(queryset)
    count = qs.update(
        status=Commission.STATUS_MANAGER_APPROVED,
        manager_approved_at=now,
        manager_approved_by=approved_by_user,
    )
    logger.info("Manager approved %s commission(s) by user %s", count, approved_by_user)
    return count


def approve_finance_commissions(queryset, approved_by_user):
    now = timezone.now()
    qs = filter_finance_approvable(queryset)
    count = qs.update(
        status=Commission.STATUS_APPROVED,
        approved_at=now,
        approved_by=approved_by_user,
    )
    logger.info("Finance approved %s commission(s) by user %s", count, approved_by_user)
    return count


def approve_commissions_admin_shortcut(queryset, approved_by_user):
    """
    Admin may advance calculated commissions directly to finance-approved
    (skips manager step when needed).
    """
    now = timezone.now()
    qs = queryset.filter(status=Commission.STATUS_CALCULATED).exclude(
        id__in=_open_dispute_commission_ids()
    )
    count = qs.update(
        status=Commission.STATUS_APPROVED,
        manager_approved_at=now,
        manager_approved_by=approved_by_user,
        approved_at=now,
        approved_by=approved_by_user,
    )
    return count


def mark_payout_run_paid(payout_run, payment_reference="", paid_by_user=None):
    """Attach finance-approved commissions in range and mark as paid."""
    if payout_run.status == PayoutRun.STATUS_PAID:
        return 0

    now = timezone.now()
    commissions = Commission.objects.filter(
        status=Commission.STATUS_APPROVED,
    ).filter(
        Q(sale__order__order_date__range=[payout_run.start_date, payout_run.end_date])
        | Q(period_start__lte=payout_run.end_date, period_end__gte=payout_run.start_date)
    ).exclude(id__in=_open_dispute_commission_ids())

    org = payout_run.organization_id
    if org:
        commissions = commissions.filter(organization_id=org)

    if payment_reference:
        payout_run.payment_reference = payment_reference

    payout_run.status = PayoutRun.STATUS_PAID
    payout_run.paid_at = now
    payout_run.save(
        update_fields=["status", "paid_at", "payment_reference"]
    )

    count = commissions.update(
        status=Commission.STATUS_PAID,
        paid_at=now,
        payout_run=payout_run,
    )
    logger.info(
        "Payout run %s marked paid: %s commission(s)",
        payout_run.pk,
        count,
    )
    return count


def order_has_locked_commissions(order):
    return Commission.objects.filter(
        sale__order=order,
        organization=getattr(order, "organization", None),
        status__in=Commission.LOCKED_STATUSES,
    ).exists()
