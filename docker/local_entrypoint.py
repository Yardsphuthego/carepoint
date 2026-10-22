"""First-run setup for the localhost-only Docker distribution."""
import os
from pathlib import Path
import secrets
import subprocess
import sys

if os.environ.get("CAREPOINT_LOCAL_SETUP") != "1":
    raise SystemExit("This entrypoint is only for the local Compose setup.")

secret_file = Path("/data/.django-secret")
try:
    with open(secret_file, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
        handle.write(secrets.token_urlsafe(64))
except FileExistsError:
    pass
os.environ["DJANGO_SECRET_KEY"] = secret_file.read_text().strip()
if not os.environ["DJANGO_SECRET_KEY"]:
    raise SystemExit("The saved secret is empty; restore /data/.django-secret from backup.")
for command in ("migrate", "create_staff_roles", "initialize_local"):
    subprocess.run([sys.executable, "manage.py", command], check=True)
os.execvp("gunicorn", ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000",
                       "--workers", "1", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-"])
