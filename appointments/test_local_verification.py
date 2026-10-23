from unittest.mock import patch
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class LocalVerificationTests(TestCase):
    def register(self):
        with patch('appointments.views.send_mail'):
            return self.client.post(reverse('register'), {
                'username': 'local-patient', 'first_name': 'Local', 'last_name': 'Patient',
                'email': 'local@example.com', 'password1': 'Another-strong-password-482!',
                'password2': 'Another-strong-password-482!',
            })

    @override_settings(DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_local_activation_link_activates_and_cannot_be_reused(self):
        response = self.register()
        self.assertContains(response, 'Activate account')
        url = response.context['local_verification_url']
        self.assertTrue(url)
        user = get_user_model().objects.get(username='local-patient')
        self.assertFalse(user.is_active)
        response = self.client.get(urlparse(url).path)
        self.assertRedirects(response, reverse('dashboard'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.client.logout()
        self.client.get(urlparse(url).path)
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(DEBUG=False, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_no_activation_link_when_debug_disabled(self):
        response = self.register()
        self.assertIsNone(response.context['local_verification_url'])
        self.assertNotContains(response, '/register/verify/')

    @override_settings(DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_no_activation_link_for_normal_email_delivery(self):
        response = self.register()
        self.assertIsNone(response.context['local_verification_url'])
        self.assertNotContains(response, '/register/verify/')
        self.assertContains(response, 'Check your inbox')
