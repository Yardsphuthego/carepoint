import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import PatientRegistrationForm, SlotSelectionForm
from .models import Appointment, AppointmentSlot, Clinician, Service
from .notifications import send_appointment_notification
from .services import (
    AppointmentError,
    book_appointment,
    cancel_appointment,
    complete_appointment,
    reschedule_appointment,
)


User = get_user_model()
logger = logging.getLogger(__name__)


def home(request):
    return redirect(settings.CAREPOINT_FRONTEND_URL)


def service_list(request):
    return redirect(settings.CAREPOINT_FRONTEND_URL.rstrip("/") + "/book")


def public_services(request):
    return JsonResponse({"services": list(
        Service.objects.filter(is_active=True).values("id", "name", "description", "duration_minutes")
    )})


def health_check(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        logger.exception("Health check could not connect to the configured database.")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = PatientRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verification_url = request.build_absolute_uri(
            reverse("verify_email", args=[uid, token])
        )
        try:
            send_mail(
                subject="Verify your Carepoint email",
                message=(
                    f"Hello {user.get_full_name() or user.username},\n\n"
                    "Verify your email address to activate your patient account:\n"
                    f"{verification_url}\n"
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except (OSError, SMTPException):
            user.delete()
            form.add_error(
                None,
                "We couldn't send the verification email. Please try again shortly.",
            )
        else:
            return render(request, "registration/verification_sent.html", {
                "console_email": settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend",
            })
    return render(request, "registration/register.html", {"form": form})


def verify_email(request, uidb64: str, token: str):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id, is_active=False)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is None or not default_token_generator.check_token(user, token):
        messages.error(
            request,
            "That verification link is invalid or expired. Please create a new account.",
        )
        return redirect("register")

    user.is_active = True
    user.save(update_fields=["is_active"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Your email is verified. Your account is ready.")
    return redirect("dashboard")


@login_required
def post_login(request):
    if Clinician.objects.filter(user=request.user, is_active=True).exists():
        return redirect("clinician_dashboard")
    if request.user.is_staff:
        return redirect("admin:index")
    return redirect("dashboard")


@login_required
def dashboard(request):
    appointments = (
        Appointment.objects.filter(patient=request.user)
        .select_related("slot__service")
        .order_by("-slot__starts_at")
    )
    return render(request, "appointments/dashboard.html", {
        "appointments": appointments,
        "upcoming_count": appointments.filter(status=Appointment.Status.SCHEDULED, slot__starts_at__gt=timezone.now()).count(),
        "completed_count": appointments.filter(status=Appointment.Status.COMPLETED).count(),
        "total_count": appointments.count(),
    })


@login_required
def book(request, service_id: int):
    service = get_object_or_404(Service, pk=service_id, is_active=True)
    form = SlotSelectionForm(request.POST or None, service_id=service.pk)
    if request.method == "POST" and form.is_valid():
        try:
            appointment = book_appointment(
                patient=request.user, slot_id=form.cleaned_data["slot"].pk
            )
        except AppointmentError as error:
            form.add_error("slot", str(error))
        else:
            email_sent = send_appointment_notification(appointment, "booked")
            messages.success(
                request,
                f"Your appointment for {appointment.slot} has been confirmed.",
            )
            if request.user.email and not email_sent:
                messages.warning(
                    request,
                    "Your booking is saved, but we couldn't send the confirmation email.",
                )
            return redirect("dashboard")
    return render(
        request,
        "appointments/appointment_form.html",
        {"form": form, "service": service, "heading": "Book an appointment"},
    )


@login_required
def cancel(request, appointment_id: int):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__service"),
        pk=appointment_id,
        patient=request.user,
    )
    return render(request, "appointments/cancel_confirm.html", {"appointment": appointment})


@login_required
@require_POST
def cancel_confirmed(request, appointment_id: int):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__service"),
        pk=appointment_id,
        patient=request.user,
    )
    try:
        cancel_appointment(appointment_id=appointment.pk, patient=request.user)
    except AppointmentError as error:
        messages.error(request, str(error))
    else:
        appointment.refresh_from_db()
        email_sent = send_appointment_notification(appointment, "cancelled")
        messages.success(request, "Your appointment has been cancelled.")
        if request.user.email and not email_sent:
            messages.warning(
                request,
                "Your cancellation is saved, but we couldn't send the email notice.",
            )
    return redirect("dashboard")


@login_required
def reschedule(request, appointment_id: int):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__service"),
        pk=appointment_id,
        patient=request.user,
        status=Appointment.Status.SCHEDULED,
    )
    form = SlotSelectionForm(
        request.POST or None,
        service_id=appointment.slot.service_id,
        label_suffix="",
    )
    if request.method == "POST" and form.is_valid():
        try:
            reschedule_appointment(
                appointment_id=appointment.pk,
                patient=request.user,
                new_slot_id=form.cleaned_data["slot"].pk,
            )
        except AppointmentError as error:
            form.add_error("slot", str(error))
        else:
            appointment.refresh_from_db()
            email_sent = send_appointment_notification(appointment, "rescheduled")
            messages.success(request, "Your appointment has been rescheduled.")
            if request.user.email and not email_sent:
                messages.warning(
                    request,
                    "Your new appointment time is saved, but we couldn't send the email notice.",
                )
            return redirect("dashboard")
    return render(
        request,
        "appointments/appointment_form.html",
        {
            "form": form,
            "service": appointment.slot.service,
            "appointment": appointment,
            "heading": "Reschedule appointment",
        },
    )


@login_required
def clinician_dashboard(request):
    clinician = get_object_or_404(
        Clinician, user=request.user, is_active=True
    )
    appointments = (
        Appointment.objects.filter(assigned_clinician=clinician)
        .select_related("patient", "slot__service")
        .order_by("-slot__starts_at")
    )
    return render(
        request,
        "appointments/clinician_dashboard.html",
        {"clinician": clinician, "appointments": appointments},
    )


@login_required
@require_POST
def clinician_complete_appointment(request, appointment_id: int):
    clinician = get_object_or_404(
        Clinician, user=request.user, is_active=True
    )
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        assigned_clinician=clinician,
    )
    try:
        complete_appointment(appointment_id=appointment.pk, clinician=clinician)
    except AppointmentError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Appointment marked as completed.")
    return redirect("clinician_dashboard")
