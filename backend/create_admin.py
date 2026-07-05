#!/usr/bin/env python
"""
Script to create an admin user for the Sales Compensation Platform.
Run from the backend directory: python create_admin.py

Credentials are read from environment variables (never hardcoded):
  ADMIN_EMAIL, ADMIN_PASSWORD
"""

from __future__ import annotations

import logging
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402

from commissions.models import UserProfile  # noqa: E402
from commissions.tenants import get_default_organization  # noqa: E402

logger = logging.getLogger("commissions")


def create_admin_user():
    """Create admin user if it does not already exist."""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD") or ""

    if not admin_email or not admin_password:
        logger.error(
            "ADMIN_EMAIL and ADMIN_PASSWORD environment variables are required."
        )
        sys.exit(1)

    if len(admin_password) < 8:
        logger.error("ADMIN_PASSWORD must be at least 8 characters.")
        sys.exit(1)

    existing_user = User.objects.filter(email=admin_email).first()
    if existing_user:
        logger.info("User %s already exists (username=%s, active=%s)",
                     admin_email, existing_user.username, existing_user.is_active)
        profile = UserProfile.objects.filter(email=admin_email).first()
        if profile:
            logger.info("Profile role: %s", profile.role)
        return

    django_user = User.objects.create_user(
        username=admin_email,
        email=admin_email,
        password=admin_password,
        first_name="Admin",
        last_name="User",
        is_active=True,
    )
    logger.info("User created: %s", django_user.email)

    profile = UserProfile.objects.create(
        organization=get_default_organization(),
        email=admin_email,
        name="Admin User",
        first_name="Admin",
        last_name="User",
        role="admin",
        employee_id="ADMIN001",
        position_name="Administrator",
        title="System Administrator",
        enable_login=True,
        business_group="Company HQ",
    )
    logger.info("Profile created with role: %s", profile.role)
    logger.info(
        "Admin user created for %s. Change the password after first login.",
        admin_email,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        create_admin_user()
    except Exception:
        logger.exception("Failed to create admin user")
        sys.exit(1)
