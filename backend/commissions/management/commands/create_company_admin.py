"""Create a tenant organization and its first admin account."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from commissions.models import Organization, UserProfile


def unique_org_slug(name, requested_slug=""):
    base = slugify(requested_slug or name)[:60] or "company"
    slug = base
    suffix = 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base[:55]}-{suffix}"
        suffix += 1
    return slug


class Command(BaseCommand):
    help = "Create a company tenant and active admin login account."

    def add_arguments(self, parser):
        parser.add_argument("--company", required=True, help="Company / organization name")
        parser.add_argument("--email", required=True, help="Admin email")
        parser.add_argument("--password", required=True, help="Admin password")
        parser.add_argument("--username", default="", help="Admin username (defaults to email)")
        parser.add_argument("--name", default="", help="Admin display name")
        parser.add_argument("--employee-id", default="", help="Admin employee ID")
        parser.add_argument("--slug", default="", help="Optional organization slug")

    def handle(self, *args, **options):
        company = options["company"].strip()
        email = options["email"].strip().lower()
        password = options["password"]
        username = (options["username"] or email).strip()
        name = (options["name"] or username).strip()
        employee_id = (options["employee_id"] or username.split("@")[0]).strip()

        if not company:
            raise CommandError("--company is required")
        if not email:
            raise CommandError("--email is required")
        if UserProfile.objects.filter(email__iexact=email).exists():
            raise CommandError("A User Setup profile with this email already exists.")
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError("A Django user with this username already exists.")
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("A Django user with this email already exists.")

        slug = unique_org_slug(company, options.get("slug") or "")
        org = Organization.objects.create(name=company, slug=slug)
        first_name = name.split(" ", 1)[0] if name else ""
        last_name = name.split(" ", 1)[1] if " " in name else ""
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        UserProfile.objects.create(
            organization=org,
            enable_login=True,
            username=username,
            email=email,
            name=name,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,
            role="Admin",
            business_group="Company HQ",
        )

        self.stdout.write(self.style.SUCCESS("Company admin created."))
        self.stdout.write(f"Organization: {org.name} ({org.slug})")
        self.stdout.write(f"Admin email:  {user.email}")
