# Carepoint

Carepoint combines a Reflex landing page and sign-in popup with Django patient booking and clinic administration.

## Share Carepoint

Scan this QR code to open this GitHub repository.

<img src="docs/carepoint-github-qr.png" alt="QR code linking to the Carepoint GitHub repository" width="280">

[Download PNG](docs/carepoint-github-qr.png) · [Download SVG for printing](docs/carepoint-github-qr.svg)

## Windows without Docker (recommended for direct installation)

From PowerShell, install the two prerequisites once:

```powershell
winget install --id Python.Python.3.14 --exact --source winget
winget install --id OpenJS.NodeJS.LTS --exact --source winget
```

Inside an existing Carepoint checkout, pull the latest code and run:

```powershell
& "$env:ProgramFiles\Git\cmd\git.exe" pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-native.ps1
```

The launcher finds the standard Python/Node installations even if this terminal's PATH has not refreshed. It installs Python dependencies into separate environments, prepares a local SQLite database, creates patient/admin accounts once, starts Django and Reflex, and opens **http://localhost:3100**. The first run downloads frontend dependencies and can take several minutes.

Keep the terminal open while using Carepoint. **Ctrl+C** stops both servers. Run the same `start-native.ps1` command next time. The generated login details are printed after startup and saved in `.local-native/local-logins.txt`. Data lives in `.local-native/db.sqlite3`; do not delete `.local-native` if you want to keep accounts and bookings. This folder is excluded from Git and Docker builds. Existing passwords are never reset by the launcher. Email verification links appear in the terminal.

This mode uses ports 3100, 8100, and 8101 and cannot run alongside the Docker profile on the same ports. No Docker or WSL is required. A fresh native installation has its own passwords and database; it does not reuse Docker's data.

## Run on a friend's PC — one command

Install **Git** and **Docker Desktop** and start Docker Desktop first. This repository is private, so the GitHub account used to clone must have access. Git will prompt for authentication when needed; never put an access token into the command.

**Windows (PowerShell):**

```powershell
git clone https://github.com/Yardsphuthego/carepoint.git; if ($LASTEXITCODE -eq 0) { Set-Location carepoint; powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 }
```

**macOS / Linux:**

```sh
git clone https://github.com/Yardsphuthego/carepoint.git && cd carepoint && sh scripts/start.sh
```

Open **http://localhost:3100**. The launcher prints a patient username/password and an administrator username/password after the services are healthy. The first start downloads dependencies and builds the frontend; allow several minutes.

### Accounts and saved data

Each computer gets its own database, generated secret, and randomly generated passwords. The usernames are `carepoint.patient` and `carepoint.admin`; **passwords are different on each installation**. Accounts, services, and bookings persist in the `carepoint_local_data` Docker volume across restarts and code updates. The first launch adds sample services and future slots; it does not copy the developer's database or passwords.

To display the originally issued credentials again:

```sh
docker compose -f compose.local.yml exec web cat /data/local-logins.txt
```

If you change a password in the app, the first-run credentials file is not updated. Use the changed password. To reset an account password interactively:

```sh
docker compose -f compose.local.yml exec web python manage.py changepassword carepoint.admin
```

These are separate installations: friends will not see each other's bookings. A shared hosted server would be needed for one shared clinic database.

### Restart, update, and stop

From inside the downloaded folder, run `sh scripts/start.sh` on Mac/Linux or `powershell -File scripts/start.ps1` on Windows. This rebuilds code when needed and preserves data.

To pull updates and run on Mac/Linux:

```sh
git pull --ff-only && sh scripts/start.sh
```

On Windows:

```powershell
git pull --ff-only; if ($LASTEXITCODE -eq 0) { powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 }
```

Stop without deleting the database:

```sh
docker compose -f compose.local.yml down
```

Do not add `--volumes` / `-v` unless you intend to delete that installation's data and credentials.

### Local ports and email

The frontend uses port **3100**, and Django uses **8100**, both bound to this PC's loopback address. Use `localhost` for both so login cookies work inside the popup. The API call between containers uses `http://web:8000`, not the visitor's localhost address. No Python, Node, or MySQL installation is needed on the host.

If those ports are busy, set `CAREPOINT_FRONTEND_PORT` and `CAREPOINT_WEB_PORT` in the shell before running the launcher. Keep the same values for subsequent commands. The frontend is built with those addresses at startup.

Email is printed to the backend logs in this local setup:

```sh
docker compose -f compose.local.yml logs web
```

Newly registered users verify their account using the link in those logs. The two initial local accounts are already active. Sample slots are seeded only once; to add fresh future sample slots later, run `docker compose -f compose.local.yml exec web python manage.py seed_sample_data`.

This Compose profile is for local sharing and review, with development HTTP settings and console email. It is not an internet deployment. The existing `docker-compose.yml` below is the separate Django/MySQL server configuration; it does not start the Reflex frontend.

Troubleshooting: `docker compose -f compose.local.yml ps` and `docker compose -f compose.local.yml logs --tail=100`. The launchers require Docker Compose v2 with `up --wait` support.

## Existing application and server setup

Single-clinic appointment booking built with Django, MySQL, and [Django Unfold](https://github.com/unfoldadmin/django-unfold).

## Platform workflows

- Patients create accounts, verify their email, sign in, reset forgotten passwords, browse services and available slots, and book, view, reschedule, or cancel appointments.
- The database enforces one active booking per slot. Service schedules reject overlapping slots and slots whose length does not match the service duration.
- Reception staff manage services, slots, patients, clinician assignments, and bookings in the Unfold admin. Booking coordinators can be limited to scheduling permissions.
- Clinicians have their own sign-in and see only appointments assigned to their clinician account. They can mark a visit complete after its scheduled end time.
- Booking, cancellation, assignment, and reminder emails use SMTP. A management command sends reminders for appointments in the next 24 hours.
- Login attempts are limited with django-axes. Patient pages are scoped to the signed-in patient.

Bookings collect contact and appointment details only; the system does not collect clinical notes or a reason for visit.

## Run locally

Python 3.12+ is required. SQLite is the default for local development:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_sample_data
python manage.py create_staff_roles
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/services/` for patient booking and `http://127.0.0.1:8000/admin/` for staff administration. Local email is printed to the development server console. `seed_sample_data` creates sample services and future slots; do not run it on a clinic's production database.

## Container deployment

Docker Compose runs Django/Gunicorn and MySQL 8.4. Copy the environment template and replace every placeholder before starting:

```sh
cp .env.example .env
```

Generate a strong key with `python -c "import secrets; print(secrets.token_urlsafe(50))"`. Set it as `DJANGO_SECRET_KEY`, replace the database and SMTP passwords, and set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to the real host and HTTPS origin. Configure a trusted SMTP service; the example SMTP values do not send mail.

```sh
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

The web port is bound to localhost for a TLS-terminating reverse proxy to expose. Run behind HTTPS, keep MySQL private, and restrict access to the host and admin interface. After sign-in, add services and appointment slots in **Services** (slots can be managed inline), create staff users, and add each clinician with their service permissions. Assign the **Clinic administrators** or **Booking coordinators** group to appropriate staff, and set their account's Staff status so they can sign in to Django admin. Clinicians use the regular sign-in page and the **Clinician workspace** link. Patient self-registration sends an email verification link; the account is not usable until it is verified.

Run database changes as a single deployment/release step before scaling web workers. The Compose volume persists MySQL data, but is not a backup. Schedule encrypted, off-host database backups and regularly test restores. Run `python manage.py send_appointment_reminders` hourly from a trusted scheduler; the command is idempotent for each appointment.

## MySQL without Docker

Set `DB_ENGINE=django.db.backends.mysql`, `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and `DB_PORT` in the process environment. The database must use `utf8mb4`. Then run `migrate`, `create_staff_roles`, and `createsuperuser` before starting Gunicorn.

## Operations and validation

```sh
python manage.py check
python manage.py test appointments
python manage.py check --deploy
```

The `/health/` endpoint checks database connectivity. Static assets are served by WhiteNoise; use a reverse proxy or managed platform for TLS. Configure SMTP before relying on email verification, password reset, or appointment notifications.

## Production-readiness boundary

The code includes production-oriented authentication, authorization, database constraints, HTTPS settings, email delivery, health checks, and a container setup. A clinic must still configure and test its real domain, TLS proxy, SMTP, backup/restore, monitoring, and deployment process. Review applicable Botswana privacy and health-data obligations with the clinic's responsible staff before entering patient information. This application is an appointment scheduler, not a medical-record system, and is not certified for clinical data storage.

## Reflex landing page

The new Docmed-inspired Carepoint landing page is in `frontend/`. See [frontend/README.md](frontend/README.md) for setup. Run it on http://localhost:3000 alongside Django on http://127.0.0.1:8000; its appointment buttons link to the existing booking workflows.
