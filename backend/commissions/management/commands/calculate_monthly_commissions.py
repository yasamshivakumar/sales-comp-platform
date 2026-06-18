"""Run month-end commission calculation for all orders in a calendar month."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from commissions.models import Organization
from commissions.plan_periods import month_bounds
from commissions.services import recalculate_orders_in_range


class Command(BaseCommand):
    help = (
        "Recalculate commissions for every order in a calendar month. "
        "Run on the last day of the month (or after) so only that month's "
        "compensation plan applies."
    )

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=None, help="Calendar year (default: today)")
        parser.add_argument("--month", type=int, default=None, help="Month 1-12 (default: today)")
        parser.add_argument("--org-id", type=int, default=None, help="Organization ID")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace approved commissions too",
        )

    def handle(self, *args, **options):
        today = date.today()
        year = options["year"] or today.year
        month = options["month"] or today.month
        if month < 1 or month > 12:
            raise CommandError("month must be 1-12")

        start, end = month_bounds(year, month)

        if options["org_id"]:
            organization = Organization.objects.filter(pk=options["org_id"]).first()
            if not organization:
                raise CommandError(f"Organization {options['org_id']} not found")
        else:
            organization = Organization.objects.order_by("pk").first()

        self.stdout.write(
            f"Recalculating commissions for {start.strftime('%B %Y')} "
            f"({start} to {end})"
        )

        stats = recalculate_orders_in_range(
            start,
            end,
            force=options["force"],
            organization=organization,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: processed={stats['processed']} "
                f"skipped_approved={stats['skipped_approved']} "
                f"failed={stats['failed']}"
            )
        )
