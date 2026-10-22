from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Service(models.Model):
    name: str = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Clinician(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clinician_profile",
    )
    services = models.ManyToManyField(Service, related_name="clinicians")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name", "user__username"]

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.get_username()


class AppointmentSlot(models.Model):
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name="slots"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_booked = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["service", "starts_at"], name="unique_service_slot_start"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.starts_at and self.starts_at <= timezone.now():
            raise ValidationError({"starts_at": "Appointment slots must be in the future."})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The end time must be after the start time."})
        if self.starts_at and self.ends_at and self.service_id:
            duration = (self.ends_at - self.starts_at).total_seconds() / 60
            if duration != self.service.duration_minutes:
                raise ValidationError(
                    {
                        "ends_at": (
                            f"This service requires a {self.service.duration_minutes}-minute slot."
                        )
                    }
                )
            overlapping_slots = AppointmentSlot.objects.filter(
                service_id=self.service_id,
                starts_at__lt=self.ends_at,
                ends_at__gt=self.starts_at,
            )
            if self.pk:
                overlapping_slots = overlapping_slots.exclude(pk=self.pk)
            if overlapping_slots.exists():
                raise ValidationError(
                    "This time overlaps another slot for the same service."
                )

    def __str__(self) -> str:
        return f"{self.service} — {timezone.localtime(self.starts_at):%a %d %b, %H:%M}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    slot: AppointmentSlot = models.ForeignKey(
        AppointmentSlot, on_delete=models.PROTECT, related_name="appointments"
    )
    active_slot = models.OneToOneField(
        AppointmentSlot,
        on_delete=models.PROTECT,
        related_name="active_appointment",
        null=True,
        blank=True,
        editable=False,
    )
    assigned_clinician = models.ForeignKey(
        Clinician,
        on_delete=models.SET_NULL,
        related_name="appointments",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.SCHEDULED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["slot__starts_at"]
        indexes = [
            models.Index(fields=["status", "slot"]),
            models.Index(fields=["patient", "status"]),
        ]

    def clean(self) -> None:
        super().clean()
        if self.assigned_clinician_id and self.slot_id:
            clinician = self.assigned_clinician
            if not clinician.is_active:
                raise ValidationError(
                    {"assigned_clinician": "Choose an active clinician."}
                )
            if not clinician.services.filter(pk=self.slot.service_id).exists():
                raise ValidationError(
                    {
                        "assigned_clinician": (
                            "This clinician is not assigned to the appointment service."
                        )
                    }
                )
    def __str__(self) -> str:
        return f"{self.patient} — {self.slot}"

    @property
    def is_upcoming(self) -> bool:
        return self.status == self.Status.SCHEDULED and self.slot.starts_at > timezone.now()

    @property
    def can_be_completed(self) -> bool:
        return (
            self.status == self.Status.SCHEDULED
            and self.slot.ends_at <= timezone.now()
        )
