from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse


class AdminNavigationTests(TestCase):
    def test_navigation_and_unfold_forms_across_management_pages(self):
        user = get_user_model().objects.create_superuser('nav-admin', password='test-password')
        self.client.force_login(user)
        for name in (
            'index', 'appointments_appointment_changelist',
            'appointments_clinician_changelist', 'appointments_clinician_add',
            'appointments_appointmentslot_changelist', 'appointments_service_changelist',
            'auth_user_changelist', 'auth_user_add', 'auth_group_changelist',
            'auth_group_add', 'axes_accessattempt_changelist',
            'axes_accesslog_changelist', 'axes_accessfailurelog_changelist',
            'password_change',
        ):
            with self.subTest(page=name):
                response = self.client.get(reverse('admin:' + name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'aria-label="Clinic navigation"')
                self.assertContains(response, 'appointments/admin.')
                self.assertNotContains(response, 'sidebarToggle()')
        response = self.client.get(reverse('admin:appointments_clinician_changelist'))
        self.assertContains(response, 'aria-current="page">Doctors')
        self.assertContains(response, reverse('admin:appointments_clinician_add'))

    def test_restricted_staff_only_see_authorized_sections(self):
        user = get_user_model().objects.create_user('booking-staff', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_appointment'))
        self.client.force_login(user)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, reverse('admin:appointments_appointment_changelist'))
        self.assertNotContains(response, reverse('admin:auth_user_changelist'))
        self.assertNotContains(response, reverse('admin:appointments_clinician_changelist'))
        self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code, 403)
