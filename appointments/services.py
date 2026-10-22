from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, AppointmentSlot


class AppointmentError(Exception):
    pass


def book_appointment(*, patient, slot_id: int) -> Appointment:
    try:
        with transaction.atomic():
            slot = AppointmentSlot.objects.select_for_update().get(pk=slot_id)
            if not slot.service.is_active or slot.starts_at <= timezone.now():
                raise AppointmentError("That appointment time is no longer bookable.")
            if slot.is_booked:
                raise AppointmentError("That appointment time has already been booked.")

            appointment = Appointment.objects.create(
                patient=patient, slot=slot, active_slot=slot
            )
            slot.is_booked = True
            slot.save(update_fields=["is_booked"])
    except IntegrityError as error:
        raise AppointmentError("That appointment time has already been booked.") from error
    return appointment


@transaction.atomic
def cancel_appointment(*, appointment_id: int, patient=None) -> Appointment:
    appointments = Appointment.objects
    if patient is not None:
        appointments = appointments.filter(patient=patient)
    appointment = appointments.select_related("slot").get(pk=appointment_id)
    slot = AppointmentSlot.objects.select_for_update().get(pk=appointment.slot_id)
    appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

    if appointment.status != Appointment.Status.SCHEDULED:
        raise AppointmentError("Only scheduled appointments can be cancelled.")
    if slot.starts_at <= timezone.now():
        raise AppointmentError("Past appointments cannot be cancelled.")

    appointment.status = Appointment.Status.CANCELLED
    appointment.active_slot = None
    appointment.save(update_fields=["status", "active_slot"])
    slot.is_booked = False
    slot.save(update_fields=["is_booked"])
    return appointment


@transaction.atomic
def complete_appointment(*, appointment_id: int, clinician=None) -> Appointment:
    appointments = Appointment.objects.select_related("slot")
    if clinician is not None:
        appointments = appointments.filter(assigned_clinician=clinician)
    appointment = appointments.select_for_update().get(pk=appointment_id)
    slot = AppointmentSlot.objects.select_for_update().get(pk=appointment.slot_id)
    if appointment.status != Appointment.Status.SCHEDULED:
        raise AppointmentError("Only scheduled appointments can be completed.")
    if slot.ends_at > timezone.now():
        raise AppointmentError("An appointment can only be completed after it ends.")

    appointment.status = Appointment.Status.COMPLETED
    appointment.active_slot = None
    appointment.save(update_fields=["status", "active_slot"])
    slot.is_booked = False
    slot.save(update_fields=["is_booked"])
    return appointment


@transaction.atomic
def reschedule_appointment(*, appointment_id: int, patient, new_slot_id: int) -> Appointment:
    appointment = Appointment.objects.select_related("slot").get(
        pk=appointment_id, patient=patient
    )
    slot_ids = sorted({appointment.slot_id, new_slot_id})
    locked_slots = {
        slot.pk: slot
        for slot in AppointmentSlot.objects.filter(pk__in=slot_ids)
        .order_by("pk")
        .select_for_update()
    }
    if len(locked_slots) != len(slot_ids):
        raise AppointmentSlot.DoesNotExist

    old_slot = locked_slots[appointment.slot_id]
    new_slot = locked_slots[new_slot_id]
    appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
    if appointment.status != Appointment.Status.SCHEDULED:
        raise AppointmentError("Only scheduled appointments can be rescheduled.")
    if old_slot.starts_at <= timezone.now():
        raise AppointmentError("Past appointments cannot be rescheduled.")
    if new_slot.pk == old_slot.pk:
        return appointment
    if new_slot.service_id != old_slot.service_id or not new_slot.service.is_active:
        raise AppointmentError("Choose an available time for the same service.")
    if new_slot.starts_at <= timezone.now() or new_slot.is_booked:
        raise AppointmentError("That appointment time is no longer available.")

    old_slot.is_booked = False
    new_slot.is_booked = True
    AppointmentSlot.objects.bulk_update([old_slot, new_slot], ["is_booked"])
    appointment.slot = new_slot
    appointment.active_slot = new_slot
    appointment.reminder_sent_at = None
    appointment.save(update_fields=["slot", "active_slot", "reminder_sent_at"])
    return appointment
