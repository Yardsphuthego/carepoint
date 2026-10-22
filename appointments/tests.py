from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlparse

from .models import Appointment, AppointmentSlot, Clinician, Service


class AppointmentFlowTests(TestCase):
    def setUp(self) -> None:
        self.patient = User.objects.create_user(
            username="patient-one",
            password="Test-password-873!",
            email="patient@example.com",
        )
        self.other_patient = User.objects.create_user(
            username="patient-two",
            password="Test-password-873!",
            email="other@example.com",
        )
        self.service = Service.objects.create(
            name="General consultation", duration_minutes=30
        )
        self.first_slot = self.create_slot(days=2)
        self.second_slot = self.create_slot(days=3)

    def create_slot(self, *, days: int) -> AppointmentSlot:
        starts_at = timezone.now() + timedelta(days=days)
        starts_at = starts_at.replace(minute=0, second=0, microsecond=0)
        return AppointmentSlot.objects.create(
            service=self.service,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=self.service.duration_minutes),
        )

    @override_settings(CAREPOINT_FRONTEND_URL="http://localhost:3000")
    def test_home_redirects_to_reflex_landing_page(self):
        self.assertRedirects(
            self.client.get(reverse("home")),
            "http://localhost:3000",
            fetch_redirect_response=False,
        )

    @override_settings(CAREPOINT_FRONTEND_URL="http://localhost:3000")
    def test_services_redirects_to_reflex_booking(self):
        self.assertRedirects(self.client.get(reverse("services")),
                             "http://localhost:3000/book", fetch_redirect_response=False)

    def test_public_services_only_lists_active_services(self):
        Service.objects.create(name="Hidden service", duration_minutes=30, is_active=False)
        response = self.client.get(reverse("public_services"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["services"], [{
            "id": self.service.pk, "name": "General consultation",
            "description": self.service.description, "duration_minutes": 30,
        }])

    def test_slot_rejects_overlapping_service_times(self) -> None:
        overlapping = AppointmentSlot(
            service=self.service,
            starts_at=self.first_slot.starts_at + timedelta(minutes=15),
            ends_at=self.first_slot.starts_at + timedelta(minutes=45),
        )

        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_slot_rejects_service_duration_mismatch(self) -> None:
        wrong_duration = AppointmentSlot(
            service=self.service,
            starts_at=self.first_slot.starts_at + timedelta(days=1),
            ends_at=self.first_slot.starts_at + timedelta(days=1, minutes=45),
        )

        with self.assertRaises(ValidationError):
            wrong_duration.full_clean()

    def test_patient_can_book_and_view_an_appointment(self) -> None:
        self.client.force_login(self.patient)

        response = self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment = Appointment.objects.get(patient=self.patient)
        self.assertEqual(appointment.slot, self.first_slot)
        self.assertEqual(appointment.active_slot, self.first_slot)
        self.first_slot.refresh_from_db()
        self.assertTrue(self.first_slot.is_booked)
        self.assertContains(self.client.get(reverse("dashboard")), "General consultation")

    def test_database_prevents_two_active_appointments_for_one_slot(self) -> None:
        Appointment.objects.create(
            patient=self.patient,
            slot=self.first_slot,
            active_slot=self.first_slot,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(
                patient=self.other_patient,
                slot=self.first_slot,
                active_slot=self.first_slot,
            )

    def test_a_booked_slot_cannot_be_booked_by_another_patient(self) -> None:
        self.client.force_login(self.patient)
        self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )

        self.client.force_login(self.other_patient)
        response = self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Appointment.objects.filter(slot=self.first_slot).count(), 1)

    def test_patient_can_cancel_and_the_slot_can_be_rebooked(self) -> None:
        self.client.force_login(self.patient)
        self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )
        appointment = Appointment.objects.get(patient=self.patient)

        response = self.client.post(
            reverse("confirm_cancel_appointment", args=[appointment.pk])
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.first_slot.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertIsNone(appointment.active_slot)
        self.assertFalse(self.first_slot.is_booked)

        self.client.force_login(self.other_patient)
        self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )
        self.assertEqual(
            Appointment.objects.filter(
                slot=self.first_slot, status=Appointment.Status.SCHEDULED
            ).count(),
            1,
        )

    def test_patient_can_reschedule_and_release_the_previous_slot(self) -> None:
        self.client.force_login(self.patient)
        self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )
        appointment = Appointment.objects.get(patient=self.patient)

        response = self.client.post(
            reverse("reschedule_appointment", args=[appointment.pk]),
            {"slot": self.second_slot.pk},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.first_slot.refresh_from_db()
        self.second_slot.refresh_from_db()
        self.assertEqual(appointment.slot, self.second_slot)
        self.assertEqual(appointment.active_slot, self.second_slot)
        self.assertFalse(self.first_slot.is_booked)
        self.assertTrue(self.second_slot.is_booked)

    def test_booking_sends_email_confirmation(self) -> None:
        self.client.force_login(self.patient)

        self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["patient@example.com"])
        self.assertIn("confirmed", mail.outbox[0].body)

    def test_patient_cannot_view_another_patients_appointment_actions(self) -> None:
        self.client.force_login(self.patient)
        self.client.post(
            reverse("book", args=[self.service.pk]), {"slot": self.first_slot.pk}
        )
        appointment = Appointment.objects.get(patient=self.patient)
        self.client.force_login(self.other_patient)

        response = self.client.get(
            reverse("cancel_appointment", args=[appointment.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_patient_can_register(self) -> None:
        response = self.client.post(
            reverse("register"),
            {
                "username": "new-patient",
                "first_name": "New",
                "last_name": "Patient",
                "email": "new@example.com",
                "password1": "Another-strong-password-482!",
                "password2": "Another-strong-password-482!",
            },
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="new-patient")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        verification_url = next(
            line
            for line in mail.outbox[0].body.splitlines()
            if "/register/verify/" in line
        )
        response = self.client.get(urlparse(verification_url).path)

        self.assertRedirects(response, reverse("dashboard"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_password_reset_sends_email(self) -> None:
        response = self.client.post(
            reverse("password_reset"), {"email": self.patient.email}
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password", mail.outbox[0].subject.lower())

    def test_unfold_staff_dashboard_is_available_to_staff(self) -> None:
        staff = User.objects.create_superuser(
            username="clinic-admin",
            email="admin@example.com",
            password="Test-password-873!",
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carepoint")
        self.assertContains(response, "Care that fits your life.")
        self.assertContains(response, "Clinic overview")

    def test_clinician_only_sees_assigned_appointments(self) -> None:
        clinician_user = User.objects.create_user(
            username="clinician-one",
            password="Test-password-873!",
            first_name="Casey",
            last_name="Care",
        )
        clinician = Clinician.objects.create(user=clinician_user)
        clinician.services.add(self.service)
        Appointment.objects.create(
            patient=self.patient,
            slot=self.first_slot,
            active_slot=self.first_slot,
            assigned_clinician=clinician,
        )
        self.client.force_login(clinician_user)

        response = self.client.get(reverse("clinician_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "patient@example.com")
        self.assertNotContains(response, "other@example.com")

    def test_clinician_can_complete_only_an_ended_assigned_appointment(self) -> None:
        clinician_user = User.objects.create_user(
            username="clinician-two", password="Test-password-873!"
        )
        clinician = Clinician.objects.create(user=clinician_user)
        clinician.services.add(self.service)
        self.first_slot.starts_at = timezone.now() - timedelta(hours=2)
        self.first_slot.ends_at = timezone.now() - timedelta(hours=1)
        self.first_slot.is_booked = True
        self.first_slot.save()
        appointment = Appointment.objects.create(
            patient=self.patient,
            slot=self.first_slot,
            active_slot=self.first_slot,
            assigned_clinician=clinician,
        )
        self.client.force_login(clinician_user)

        response = self.client.post(
            reverse("clinician_complete_appointment", args=[appointment.pk])
        )

        self.assertRedirects(response, reverse("clinician_dashboard"))
        appointment.refresh_from_db()
        self.first_slot.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        self.assertIsNone(appointment.active_slot)
        self.assertFalse(self.first_slot.is_booked)

    def test_health_endpoint_reports_database_availability(self) -> None:
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})


class AppointmentReminderTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reminder_command_sends_once_and_records_success(self) -> None:
        patient = User.objects.create_user(
            username="reminder-patient",
            password="Test-password-873!",
            email="reminder@example.com",
        )
        service = Service.objects.create(name="Vaccination")
        starts_at = timezone.now() + timedelta(hours=12)
        slot = AppointmentSlot.objects.create(
            service=service,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            is_booked=True,
        )
        appointment = Appointment.objects.create(patient=patient, slot=slot)

        call_command("send_appointment_reminders")

        appointment.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reminder@example.com"])
        self.assertIsNotNone(appointment.reminder_sent_at)

        call_command("send_appointment_reminders")
        self.assertEqual(len(mail.outbox), 1)


class PatientEmbeddingTests(TestCase):
    @override_settings(CAREPOINT_FRONTEND_URL="https://carepoint.example", DEBUG=False)
    def test_patient_forms_allow_only_configured_frontend(self):
        response = self.client.get(reverse("login"), secure=True)
        self.assertEqual(response["Content-Security-Policy"], "frame-ancestors 'self' https://carepoint.example")
        self.assertNotIn("X-Frame-Options", response)

    def test_admin_keeps_frame_protection(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response["X-Frame-Options"], "DENY")


class PatientEntryRoutingTests(TestCase):
    @override_settings(CAREPOINT_FRONTEND_URL="http://localhost:3000")
    def test_direct_browser_login_opens_frontend_and_preserves_booking(self):
        response = self.client.get("/accounts/login/?next=/appointments/book/1/", HTTP_SEC_FETCH_DEST="document")
        self.assertEqual(response.status_code, 302)
        from urllib.parse import parse_qs, urlparse
        target = urlparse(response.url)
        self.assertEqual(target.netloc, "localhost:3000")
        self.assertEqual(parse_qs(target.query)["portal"], ["/accounts/login/?next=/appointments/book/1/"])

    def test_popup_login_still_serves_form(self):
        response = self.client.get("/accounts/login/", HTTP_SEC_FETCH_DEST="iframe")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken")
