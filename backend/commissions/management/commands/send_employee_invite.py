"""Send or resend an invite link for an employee login."""

from django.core.management.base import BaseCommand, CommandError

from commissions.invites import create_user_invite, build_invite_url
from commissions.models import UserProfile


class Command(BaseCommand):
    help = "Send or resend an invite for a User Setup profile by email or employee_id."

    def add_arguments(self, parser):
        parser.add_argument("identifier", help="User email or employee_id")
        parser.add_argument(
            "--print-link",
            action="store_true",
            help="Print the invite link to stdout after creating it.",
        )

    def handle(self, *args, **options):
        identifier = options["identifier"].strip()
        profile = (
            UserProfile.objects.filter(email__iexact=identifier).first()
            or UserProfile.objects.filter(employee_id__iexact=identifier).first()
        )
        if not profile:
            raise CommandError(f"No User Setup profile found for '{identifier}'")
        if not profile.email:
            raise CommandError("Profile has no email address.")

        if not profile.enable_login:
            profile.enable_login = True
            profile.save(update_fields=["enable_login"])

        invite, token, sent = create_user_invite(profile)
        if not invite:
            raise CommandError("Could not create invite.")

        self.stdout.write(
            self.style.SUCCESS(
                f"Invite {'sent' if sent else 'created'} for {profile.email}"
            )
        )
        if options["print_link"]:
            self.stdout.write(build_invite_url(token))
