"""Backfill business_group and currency on existing orders."""

from django.core.management.base import BaseCommand

from commissions.models import Order
from commissions.services import sync_order_region


class Command(BaseCommand):
    help = "Align business_group and currency on all orders (for dashboard reporting)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            help="Limit to one organization id",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many orders would change without saving",
        )

    def handle(self, *args, **options):
        qs = Order.objects.all().order_by("id")
        org_id = options.get("organization_id")
        if org_id:
            qs = qs.filter(organization_id=org_id)

        updated = 0
        for order in qs.iterator():
            before_group = str(order.business_group or "")
            before_currency = str(order.currency or "")
            if options["dry_run"]:
                sync_order_region(order, save=False)
                after_group = str(order.business_group or "")
                after_currency = str(order.currency or "")
                if after_group != before_group or after_currency != before_currency:
                    updated += 1
            else:
                result = sync_order_region(order, save=True)
                if (
                    result["business_group"] != before_group
                    or result["currency"] != before_currency
                ):
                    updated += 1

        action = "Would update" if options["dry_run"] else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} {updated} order(s)."))
