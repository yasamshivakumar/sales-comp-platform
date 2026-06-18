"""Reset login password for an employee or admin user."""

from django.core.management.base import BaseCommand, CommandError

from commissions.auth_utils import get_onboarding_password, provision_login_user
from commissions.models import UserProfile


class Command(BaseCommand):
    help = (
        "Set or reset a login password by email or employee_id. "
        "Uses DEFAULT_ONBOARDING_PASSWORD when no password argument is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "identifier",
            help="User email (e.g. sai1@gmail.com) or employee_id (e.g. sai1)",
        )
        parser.add_argument(
            "password",
            nargs="?",
            help="New password (defaults to DEFAULT_ONBOARDING_PASSWORD or DEBUG fallback)",
        )

    def handle(self, *args, **options):
        identifier = options["identifier"].strip()
        password = options.get("password") or get_onboarding_password()
        if not password:
            raise CommandError(
                "No password provided and DEFAULT_ONBOARDING_PASSWORD is not set."
            )

        profile = (
            UserProfile.objects.filter(email__iexact=identifier).first()
            or UserProfile.objects.filter(employee_id__iexact=identifier).first()
        )
        if not profile:
            raise CommandError(f"No User Setup profile found for '{identifier}'")

        if not profile.enable_login:
            self.stdout.write(
                self.style.WARNING(
                    f"Profile {profile.email} has enable_login=False — enabling login."
                )
            )
            profile.enable_login = True
            profile.save(update_fields=["enable_login"])

        user = provision_login_user(profile, reset_password=True)
        if password != get_onboarding_password():
            user.set_password(password)
            user.save()

        self.stdout.write(self.style.SUCCESS(f"Login ready for {profile.email}"))
        self.stdout.write("")
        self.stdout.write("Login with:")
        self.stdout.write(f"  Email:    {profile.email}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write("")
        self.stdout.write("Ask the user to change their password after first login.")
