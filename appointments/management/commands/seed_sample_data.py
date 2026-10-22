from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import AppointmentSlot, Service


class Command(BaseCommand):
    help = "Create sample services and appointment slots for a fresh installation."

    def handle(self, *args, **options) -> None:
        services = [
            ("General consultation", "Routine appointments with our care team.", 30),
            ("Vaccination", "Book a vaccination appointment.", 20),
            ("Women's health", "Confidential women's health appointments.", 45),
        ]
        created = 0
        for name, description, duration in services:
            service, _ = Service.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "duration_minutes": duration,
                },
            )
            for day_offset in range(1, 15):
                day = timezone.localdate() + timedelta(days=day_offset)
                if day.weekday() >= 5:
                    continue
                for hour in (9, 11, 14, 15):
                    starts_at = timezone.make_aware(
                        datetime.combine(day, time(hour=hour)),
                        timezone.get_current_timezone(),
                    )
                    _, was_created = AppointmentSlot.objects.get_or_create(
                        service=service,
                        starts_at=starts_at,
                        defaults={
                            "ends_at": starts_at + timedelta(minutes=duration)
                        },
                    )
                    created += was_created
        self.stdout.write(
            self.style.SUCCESS(
                f"Sample data ready: {len(services)} services, {created} new slots."
            )
        )
