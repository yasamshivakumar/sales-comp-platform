"""Pull HubSpot owners and deals into Incentra (users → orders → commissions)."""

from django.core.management.base import BaseCommand, CommandError

from commissions.integrations.sync import run_full_sync, test_integration
from commissions.models import ExternalIntegration


class Command(BaseCommand):
    help = (
        "Run full HubSpot sync for an organization: owners → Incentra employees, "
        "then closed-won deals → orders → commissions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--integration-id",
            type=int,
            help="ExternalIntegration id (HubSpot provider).",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            help="Organization id (uses first active HubSpot integration if no --integration-id).",
        )
        parser.add_argument("--limit", type=int, default=None, help="Max records per step.")
        parser.add_argument(
            "--test-only",
            action="store_true",
            help="Only test the HubSpot connection.",
        )

    def handle(self, *args, **options):
        integration = self._resolve_integration(options)
        if options["test_only"]:
            result = test_integration(integration)
            if not result["ok"]:
                raise CommandError(result["message"])
            self.stdout.write(self.style.SUCCESS(result["message"]))
            return

        result = run_full_sync(integration, limit=options["limit"])
        users = result["users"]["result"]
        orders = result["orders"]["result"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Users: {users.get('success', 0)} ok, {users.get('failed', 0)} failed"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Orders: {orders.get('success', 0)} ok, {orders.get('failed', 0)} failed; "
                f"commissions created: {orders.get('commissions_created', 0)}"
            )
        )

    def _resolve_integration(self, options):
        integration_id = options.get("integration_id")
        org_id = options.get("org_id")
        qs = ExternalIntegration.objects.filter(
            provider=ExternalIntegration.PROVIDER_HUBSPOT,
            is_active=True,
        )
        if integration_id:
            integration = qs.filter(pk=integration_id).first()
        elif org_id:
            integration = qs.filter(organization_id=org_id).first()
        else:
            integration = qs.first()
        if not integration:
            raise CommandError(
                "No active HubSpot integration found. Create one in Integrations "
                "with your private app access token."
            )
        return integration
