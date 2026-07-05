"""Sync Django login users for all User Setup profiles with enable_login."""

from django.core.management.base import BaseCommand

from commissions.auth_utils import get_onboarding_password, sync_all_login_users


class Command(BaseCommand):
    help = (
        "Create or repair Django login accounts for every User Setup profile "
        "with enable_login=True. Use --reset-password to apply the onboarding password."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Reset every login user to DEFAULT_ONBOARDING_PASSWORD",
        )

    def handle(self, *args, **options):
        pwd = get_onboarding_password()
        if not pwd:
            self.stderr.write(
                self.style.ERROR(
                    "No onboarding password configured. Set DEFAULT_ONBOARDING_PASSWORD "
                    "in backend/.env."
                )
            )
            return

        stats = sync_all_login_users(reset_password=options["reset_password"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete — created: {stats['created']}, "
                f"updated: {stats['updated']}, skipped: {stats['skipped']}"
            )
        )
        self.stdout.write(
            "Employees can sign in with their User Setup email and the "
            "configured onboarding password (not displayed)."
        )
        self.stdout.write("Ask users to change their password after first login.")
