import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("commissions")


def notify_admins(subject, message):
    """Send ops notification when NOTIFY_EMAILS is configured."""
    recipients = getattr(settings, "NOTIFY_EMAILS", None) or []
    if not recipients:
        return False

    from_email = settings.DEFAULT_FROM_EMAIL
    try:
        sent_count = send_mail(
            subject,
            message,
            from_email,
            recipients,
            fail_silently=False,
        )
        if sent_count <= 0:
            logger.warning("Email backend accepted 0 admin notification messages: %s", subject)
            return False
        return True
    except Exception:
        logger.exception("Failed to send notification: %s", subject)
        return False


def notify_user(email, subject, message, *, reply_to=None):
    """Send notification to a single user when email backend is configured."""
    if not email:
        return False
    from_email = settings.DEFAULT_FROM_EMAIL
    try:
        sent_count = send_mail(
            subject,
            message,
            from_email,
            [email],
            fail_silently=False,
            reply_to=reply_to or None,
        )
        if sent_count <= 0:
            logger.warning("Email backend accepted 0 user notification messages to %s", email)
            return False
        return True
    except Exception:
        logger.exception("Failed to send user notification to %s", email)
        return False


def notify_commission_manager_approved(count, start_date=None, end_date=None):
    period = ""
    if start_date and end_date:
        period = f" for {start_date} to {end_date}"
    notify_admins(
        f"[Incentra] {count} commission(s) manager-approved{period}",
        f"{count} commission record(s) were approved by a sales manager{period}.\n"
        "Finance review is required before payroll export.",
    )


def notify_commission_finance_approved(count, start_date=None, end_date=None):
    period = ""
    if start_date and end_date:
        period = f" for {start_date} to {end_date}"
    notify_admins(
        f"[Incentra] {count} commission(s) finance-approved{period}",
        f"{count} commission record(s) are ready for payroll{period}.",
    )
    notify_user(
        getattr(settings, "FINANCE_NOTIFY_EMAIL", ""),
        f"[Incentra] {count} commissions ready for payout{period}",
        f"Finance approval completed for {count} commission(s){period}.",
    )


def notify_commission_paid(payout_run, count):
    notify_admins(
        f"[Incentra] Payout run paid: {payout_run.name}",
        f"Payout run '{payout_run.name}' marked paid.\n"
        f"Reference: {payout_run.payment_reference or 'n/a'}\n"
        f"Commissions paid: {count}",
    )


def notify_commission_dispute(dispute):
    comm = dispute.commission
    notify_admins(
        f"[Incentra] Commission dispute #{dispute.pk}",
        f"Employee {comm.employee.name} opened a dispute on commission #{comm.pk}.\n\n"
        f"Message: {dispute.message}",
    )
    if dispute.raised_by and dispute.raised_by.email:
        notify_user(
            dispute.raised_by.email,
            "[Incentra] Dispute submitted",
            "Your commission dispute was submitted and is under review.",
        )
