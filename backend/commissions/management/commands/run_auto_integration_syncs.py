"""Run automatic CRM sync for integrations that are due."""

from django.core.management.base import BaseCommand

from commissions.integrations.sync import run_due_auto_integration_syncs


class Command(BaseCommand):
    help = (
        "Queue or run automatic CRM sync (users → orders → commissions) "
        "for integrations with auto_sync_enabled."
    )

    def handle(self, *args, **options):
        summary = run_due_auto_integration_syncs()
        count = summary.get("count", 0)
        if count:
            self.stdout.write(
                self.style.SUCCESS(f"Triggered auto sync for {count} integration(s).")
            )
        else:
            self.stdout.write("No integrations due for auto sync.")
