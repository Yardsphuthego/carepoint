"""Run Carepoint locally without Docker. Keep this terminal open; Ctrl+C stops it."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / '.local-native'


def setup_python(name, requirements):
    directory = DATA / name
    python = directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print(f'Creating {name} environment...', flush=True)
        venv.EnvBuilder(with_pip=True).create(directory)
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = directory / 'requirements.sha256'
    if not stamp.exists() or stamp.read_text() != digest:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
        stamp.write_text(digest)
    return str(python)


def environment():
    DATA.mkdir(exist_ok=True)
    secret = DATA / '.django-secret'
    if not secret.exists():
        with open(secret, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as handle:
            handle.write(secrets.token_urlsafe(64))
    env = os.environ.copy()
    env.update({
        'DJANGO_SECRET_KEY': secret.read_text().strip(),
        'DJANGO_DEBUG': 'True',
        'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1',
        'DB_ENGINE': 'django.db.backends.sqlite3', 'DB_NAME': str(DATA / 'db.sqlite3'),
        'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend',
        'CAREPOINT_LOCAL_SETUP': '1', 'CAREPOINT_LOCAL_CREDENTIALS': str(DATA / 'local-logins.txt'),
        'CAREPOINT_FRONTEND_URL': 'http://localhost:3100',
        'CAREPOINT_BOOKING_URL': 'http://localhost:8100',
        'CAREPOINT_API_INTERNAL_URL': 'http://localhost:8100',
        'REFLEX_API_URL': 'http://localhost:8101', 'REFLEX_DEPLOY_URL': 'http://localhost:3100',
        'REFLEX_FRONTEND_PORT': '3100', 'REFLEX_BACKEND_PORT': '8101',
        'REFLEX_BACKEND_HOST': '127.0.0.1', 'REFLEX_TELEMETRY_ENABLED': 'false',
        'PYTHONUNBUFFERED': '1',
    })
    return env


def ready(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def main():
    if sys.version_info < (3, 12):
        raise SystemExit('Python 3.12 or newer is required. Install Python 3.14 and retry.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--setup-only', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    env = environment()
    backend = setup_python('backend-venv', ROOT / 'requirements.txt')
    frontend = setup_python('frontend-venv', ROOT / 'frontend/requirements.txt')
    for command in ['migrate', 'create_staff_roles', 'initialize_local']:
        subprocess.run([backend, 'manage.py', command], cwd=ROOT, env=env, check=True)
    if args.setup_only:
        print('Native setup complete.', flush=True)
        return
    for port in (3100, 8100, 8101):
        with socket.socket() as check:
            if check.connect_ex(('127.0.0.1', port)) == 0:
                raise SystemExit(f'Port {port} is already in use. Close the previous Carepoint terminal or stop Docker Carepoint, then retry.')
    children = []
    try:
        children.append(subprocess.Popen([backend, 'manage.py', 'runserver', '127.0.0.1:8100', '--noreload'], cwd=ROOT, env=env))
        children.append(subprocess.Popen([frontend, '-m', 'reflex', 'run', '--env', 'dev', '--frontend-port', '3100', '--backend-port', '8101', '--backend-host', '127.0.0.1'], cwd=ROOT / 'frontend', env=env))
        deadline = time.monotonic() + 900
        while not all(ready(url) for url in ['http://localhost:8100/health/', 'http://localhost:3100/']):
            if any(child.poll() is not None for child in children):
                raise RuntimeError('A server stopped during startup. See its error above.')
            if time.monotonic() > deadline:
                raise RuntimeError('Startup timed out. Check the output above.')
            time.sleep(2)
        print('\nCarepoint is ready: http://localhost:3100\nKeep this terminal open. Press Ctrl+C to stop.\n', flush=True)
        if not os.environ.get('GITHUB_ACTIONS'):
            print((DATA / 'local-logins.txt').read_text(), flush=True)
        if not args.no_browser:
            webbrowser.open('http://localhost:3100')
        while all(child.poll() is None for child in children):
            time.sleep(2)
        raise RuntimeError('A Carepoint server stopped. See its error above.')
    except KeyboardInterrupt:
        print('\nStopping Carepoint...')
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == '__main__':
    main()
