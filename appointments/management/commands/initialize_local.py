"""Provision accounts once per local Docker database, never reset existing users."""
import os
from pathlib import Path
import secrets

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction


class Command(BaseCommand):
    help = "Initialize the isolated localhost Docker installation."

    def handle(self, *args, **options):
        if os.environ.get("CAREPOINT_LOCAL_SETUP") != "1":
            raise CommandError("Only enabled by the local Docker setup.")
        credential_path = Path(os.environ.get("CAREPOINT_LOCAL_CREDENTIALS", "/data/local-logins.txt"))
        User = get_user_model()
        # The volume and existing accounts are the source of truth on restarts.
        if credential_path.exists():
            if not all(User.objects.filter(username=name).exists() for name in ("carepoint.patient", "carepoint.admin")):
                raise CommandError("Saved logins and database do not match. Restore the complete data volume.")
            self.stdout.write("Local accounts already initialized; passwords unchanged.")
            return
        if User.objects.exists():
            raise CommandError("Existing users found; refusing to overwrite accounts or create shared credentials.")
        with transaction.atomic():
            credentials = []
            for username, staff, name in (("carepoint.patient", False, "Patient"), ("carepoint.admin", True, "Admin")):
                password = secrets.token_urlsafe(18)
                User.objects.create_user(username=username, password=password, first_name=name,
                                         is_active=True, is_staff=staff, is_superuser=staff)
                credentials.append(f"{username}\nPassword: {password}\n")
            call_command("seed_sample_data", stdout=self.stdout)
            # Exclusive creation avoids overwriting previously issued credentials.
            with open(credential_path, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
                handle.write("Carepoint local logins (generated on first start)\n\n" + "\n".join(credentials))
        self.stdout.write("Local accounts created. Run the launcher to display their login details.")
