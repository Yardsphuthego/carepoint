import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase


class LocalSetupTests(TestCase):
    def test_first_run_creates_working_accounts_and_restart_keeps_passwords(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'local-logins.txt'
            with patch.dict(os.environ, {'CAREPOINT_LOCAL_SETUP': '1', 'CAREPOINT_LOCAL_CREDENTIALS': str(path)}):
                call_command('initialize_local')
                initial = path.read_text()
                passwords = {}
                lines = initial.splitlines()
                for index, line in enumerate(lines):
                    if line.startswith('carepoint.'):
                        passwords[line] = lines[index + 1].removeprefix('Password: ')
                User = get_user_model()
                self.assertTrue(User.objects.get(username='carepoint.admin').is_superuser)
                self.assertFalse(User.objects.get(username='carepoint.patient').is_staff)
                for name, password in passwords.items():
                    self.assertTrue(User.objects.get(username=name).check_password(password))
                call_command('initialize_local')
                self.assertEqual(path.read_text(), initial)
                self.assertEqual(User.objects.count(), 2)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_existing_users_are_not_modified(self):
        user = get_user_model().objects.create_user(username='existing', password='Existing-password-100!')
        with TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'CAREPOINT_LOCAL_SETUP': '1', 'CAREPOINT_LOCAL_CREDENTIALS': str(Path(directory) / 'logins')}):
                with self.assertRaises(CommandError):
                    call_command('initialize_local')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Existing-password-100!'))

    def test_setup_requires_explicit_local_mode(self):
        with patch.dict(os.environ, {'CAREPOINT_LOCAL_SETUP': '0'}):
            with self.assertRaises(CommandError):
                call_command('initialize_local')
