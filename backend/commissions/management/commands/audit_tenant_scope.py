from django.core.management.base import BaseCommand

from commissions.models import (
    AuditLog,
    Commission,
    CommissionRule,
    CompensationPlan,
    Employee,
    ExternalIntegration,
    ImportJob,
    Order,
    PayoutRun,
    Sale,
    Territory,
    UserProfile,
)


class Command(BaseCommand):
    help = "Report tenant-owned rows with missing organization values."

    MODELS = [
        UserProfile,
        Employee,
        Sale,
        Commission,
        Order,
        CompensationPlan,
        Territory,
        PayoutRun,
        AuditLog,
        ExternalIntegration,
        ImportJob,
        CommissionRule,
    ]

    def handle(self, *args, **options):
        total = 0
        for model in self.MODELS:
            count = model.objects.filter(organization__isnull=True).count()
            total += count
            self.stdout.write(f"{model.__name__}: {count}")

        if total:
            self.stdout.write(self.style.WARNING(f"{total} rows need tenant backfill."))
        else:
            self.stdout.write(self.style.SUCCESS("All checked rows have organizations."))
