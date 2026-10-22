from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Appointment, AppointmentSlot, Service


def dashboard_callback(request, context):
    metrics = []
    actions = []
    if request.user.has_perm('appointments.view_appointment'):
        metrics.append({'label': 'Appointments today', 'value': Appointment.objects.filter(slot__starts_at__date=timezone.localdate(), status=Appointment.Status.SCHEDULED).count()})
        context['clinic_appointments'] = Appointment.objects.filter(slot__starts_at__gte=timezone.now(), status=Appointment.Status.SCHEDULED).select_related('patient', 'slot__service').order_by('slot__starts_at')[:6]
        actions.append({'label': 'Manage appointments', 'url': reverse('admin:appointments_appointment_changelist')})
    if request.user.has_perm('appointments.view_appointmentslot'):
        metrics.append({'label': 'Available times', 'value': AppointmentSlot.objects.filter(starts_at__gt=timezone.now(), is_booked=False, service__is_active=True).count()})
        actions.append({'label': 'Manage appointment times', 'url': reverse('admin:appointments_appointmentslot_changelist')})
    if request.user.has_perm('appointments.view_service'):
        metrics.append({'label': 'Active services', 'value': Service.objects.filter(is_active=True).count()})
        actions.append({'label': 'Manage services', 'url': reverse('admin:appointments_service_changelist')})
    if request.user.has_perm('auth.view_user'):
        metrics.append({'label': 'Patient accounts', 'value': get_user_model().objects.filter(is_staff=False, clinician_profile__isnull=True).count()})
        actions.append({'label': 'Manage accounts', 'url': reverse('admin:auth_user_changelist')})
    context.update(clinic_metrics=metrics, clinic_actions=actions)
    return context
