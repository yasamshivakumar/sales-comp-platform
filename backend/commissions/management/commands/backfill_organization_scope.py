from django.core.management.base import BaseCommand
from django.db.models import Q

from commissions.models import (
    Commission,
    CompensationPlan,
    Order,
    Sale,
    UserProfile,
)
from commissions.tenants import get_default_organization


class Command(BaseCommand):
    help = (
        "Backfill null organization FKs on core tenant tables to the default "
        "organization. Logs per-model counts. Does not alter schema nullability."
    )

    MODELS = (
        ("UserProfile", UserProfile),
        ("Order", Order),
        ("Sale", Sale),
        ("Commission", Commission),
        ("CompensationPlan", CompensationPlan),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts without writing.",
        )
        parser.add_argument(
            "--organization-slug",
            default="default",
            help="Target organization slug (default: default).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        slug = options["organization_slug"]
        if slug == "default":
            org = get_default_organization()
        else:
            from commissions.models import Organization

            org = Organization.objects.filter(slug__iexact=slug).first()
        if org is None:
            self.stderr.write(self.style.ERROR(f"Organization not found: {slug}"))
            return

        total = 0
        for label, model in self.MODELS:
            qs = model.objects.filter(Q(organization__isnull=True))
            count = qs.count()
            total += count
            if dry_run or count == 0:
                self.stdout.write(f"{label}: {count} (unchanged)")
                continue
            updated = qs.update(organization=org)
            self.stdout.write(
                self.style.SUCCESS(f"{label}: backfilled {updated} → org={org.slug}")
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry run: {total} rows would be backfilled.")
            )
        elif total == 0:
            self.stdout.write(self.style.SUCCESS("No null-organization rows on core tables."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Backfill complete. total_updated={total} org={org.slug}")
            )
