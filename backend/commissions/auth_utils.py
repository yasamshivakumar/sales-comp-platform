"""Shared helpers for Django auth user provisioning."""

from django.conf import settings
from django.contrib.auth.models import User


def get_onboarding_password():
    """
    Initial login password for employees provisioned via User Setup.

    Uses DEFAULT_ONBOARDING_PASSWORD from the environment. In DEBUG mode only,
    falls back to Welcome@123 so local dev works without extra .env setup.
    """
    pwd = (getattr(settings, "DEFAULT_ONBOARDING_PASSWORD", "") or "").strip()
    if pwd:
        return pwd
    if settings.DEBUG:
        return "Welcome@123"
    return ""


def apply_onboarding_password(django_user, *, user_created=False, force=False):
    """
    Set the initial password when configured (or DEBUG fallback exists).

    Applies on new users, when the account has no usable password, or when forced.
    Returns True if a password was set.
    """
    pwd = get_onboarding_password()
    if not pwd:
        return False
    if user_created or force or not django_user.has_usable_password():
        django_user.set_password(pwd)
        return True
    return False


def provision_login_user(profile, *, reset_password=False):
    """
    Create or update the Django auth user for a UserProfile with login enabled.

    Returns the User instance, or None when login is disabled for this profile.
    """
    if not profile or not profile.enable_login:
        return None

    email = (profile.email or "").strip().lower()
    if not email:
        return None

    username = (profile.username or email).strip()

    # Prefer the auth row already tied to this email so login and provisioning
    # stay on the same User (avoids duplicate rows when username != email).
    django_user = (
        User.objects.filter(email__iexact=email).first()
        or User.objects.filter(username__iexact=username).first()
        or User.objects.filter(username__iexact=email).first()
    )
    user_created = False
    if not django_user:
        django_user = User(
            username=username,
            email=email,
            first_name=profile.first_name or "",
            last_name=profile.last_name or "",
            is_active=True,
        )
        user_created = True

    if (
        username
        and django_user.username != username
        and not User.objects.filter(username=username).exclude(pk=django_user.pk).exists()
    ):
        django_user.username = username

    django_user.email = email
    django_user.first_name = profile.first_name or ""
    django_user.last_name = profile.last_name or ""
    django_user.is_active = True

    if reset_password:
        pwd = get_onboarding_password()
        if pwd:
            django_user.set_password(pwd)
    else:
        apply_onboarding_password(django_user, user_created=user_created)

    django_user.save()
    return django_user


def sync_all_login_users(*, reset_password=False):
    """
    Ensure every UserProfile with enable_login has a Django user and password.
    Returns counts: {created, updated, skipped, password_set}.
    """
    from .models import UserProfile

    stats = {"created": 0, "updated": 0, "skipped": 0, "password_set": 0}
    pwd = get_onboarding_password()

    for profile in UserProfile.objects.filter(enable_login=True).exclude(email=""):
        email = profile.email.strip().lower()
        username = (profile.username or email).strip()
        existed = User.objects.filter(username=username).exists() or User.objects.filter(
            email__iexact=email
        ).exists()

        user = provision_login_user(profile, reset_password=reset_password)
        if not user:
            stats["skipped"] += 1
            continue

        if not existed:
            stats["created"] += 1
        else:
            stats["updated"] += 1
        if pwd and (reset_password or user.has_usable_password()):
            stats["password_set"] += 1

    return stats
