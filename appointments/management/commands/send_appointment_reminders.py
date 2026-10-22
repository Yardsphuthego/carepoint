from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import Appointment


class Command(BaseCommand):
    help = "Email patients reminders for appointments in the next 24 hours."

    def handle(self, *args, **options) -> None:
        now = timezone.now()
        upcoming = Appointment.objects.filter(
            status=Appointment.Status.SCHEDULED,
            slot__starts_at__gt=now,
            slot__starts_at__lte=now + timedelta(hours=24),
            reminder_sent_at__isnull=True,
            patient__email__gt="",
        ).select_related("patient", "slot__service")
        sent = 0
        for appointment in upcoming:
            send_mail(
                subject="Appointment reminder",
                message=(
                    f"Hello {appointment.patient.get_full_name() or appointment.patient.username},\n\n"
                    f"This is a reminder of your {appointment.slot.service.name} appointment "
                    f"on {timezone.localtime(appointment.slot.starts_at):%A, %d %B at %H:%M}.\n"
                ),
                from_email=None,
                recipient_list=[appointment.patient.email],
                fail_silently=False,
            )
            appointment.reminder_sent_at = now
            appointment.save(update_fields=["reminder_sent_at"])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} appointment reminder(s)."))
