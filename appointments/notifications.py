import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Appointment


logger = logging.getLogger(__name__)


def send_appointment_notification(appointment: Appointment, event: str) -> bool:
    if not appointment.patient.email:
        return False

    appointment_time = timezone.localtime(appointment.slot.starts_at)
    messages = {
        "booked": (
            "Appointment confirmed",
            "Your appointment has been confirmed.",
        ),
        "rescheduled": (
            "Appointment rescheduled",
            "Your appointment time has been changed.",
        ),
        "cancelled": (
            "Appointment cancelled",
            "Your appointment has been cancelled.",
        ),
        "assigned": (
            "Clinician assigned",
            "A clinician has been assigned to your appointment.",
        ),
    }
    try:
        subject, opening = messages[event]
    except KeyError as error:
        raise ValueError(f"Unsupported appointment notification: {event}") from error

    clinician_line = ""
    if event == "assigned" and appointment.assigned_clinician_id:
        clinician_line = f"Clinician: {appointment.assigned_clinician}\n"
    body = (
        f"Hello {appointment.patient.get_full_name() or appointment.patient.username},\n\n"
        f"{opening}\n\n"
        f"Service: {appointment.slot.service.name}\n"
        f"{clinician_line}"
        f"Date and time: {appointment_time:%A, %d %B %Y at %H:%M}\n"
        f"Duration: {appointment.slot.service.duration_minutes} minutes\n\n"
        "Sign in to your Carepoint account to manage your appointments.\n"
    )
    try:
        send_mail(
            subject=f"Carepoint — {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[appointment.patient.email],
            fail_silently=False,
        )
    except (OSError, SMTPException):
        logger.exception(
            "Email notification failed for appointment %s (%s)",
            appointment.pk,
            event,
        )
        return False
    return True
