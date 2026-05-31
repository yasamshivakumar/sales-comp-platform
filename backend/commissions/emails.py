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
        send_mail(
            subject,
            message,
            from_email,
            recipients,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send notification: %s", subject)
        return False
