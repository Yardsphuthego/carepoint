from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import Group
from axes.admin import AccessAttemptAdmin, AccessLogAdmin, AccessFailureLogAdmin
from axes.models import AccessAttempt, AccessLog, AccessFailureLog
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import UserCreationForm, UserChangeForm, AdminPasswordChangeForm

from .models import Appointment, AppointmentSlot, Clinician, Service
from .notifications import send_appointment_notification
from .services import AppointmentError, cancel_appointment


User = get_user_model()
admin.site.unregister(User)
admin.site.index_title = "Clinic overview"
admin.site.enable_nav_sidebar = False
admin.site.password_change_template = "admin/password_change_form.html"
admin.site.password_change_done_template = "admin/password_change_done.html"

# Keep the third-party management screens in the same Unfold layout.
for model, base_admin in (
    (Group, GroupAdmin),
    (AccessAttempt, AccessAttemptAdmin),
    (AccessLog, AccessLogAdmin),
    (AccessFailureLog, AccessFailureLogAdmin),
):
    if admin.site.is_registered(model):
        admin.site.unregister(model)
    admin.site.register(model, type(f"Carepoint{base_admin.__name__}", (base_admin, ModelAdmin), {}))


class AppointmentSlotInline(TabularInline):
    model = AppointmentSlot
    extra = 1
    fields = ("starts_at", "ends_at", "is_booked")
    readonly_fields = ("is_booked",)


@admin.register(Service)
class ServiceAdmin(ModelAdmin):
    list_display = ("name", "duration_minutes", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    inlines = (AppointmentSlotInline,)


@admin.register(Clinician)
class ClinicianAdmin(ModelAdmin):
    list_display = ("user", "is_active", "service_list")
    list_filter = ("is_active", "services")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    filter_horizontal = ("services",)

    @admin.display(description="Services")
    def service_list(self, obj: Clinician) -> str:
        return ", ".join(obj.services.values_list("name", flat=True))


@admin.register(User)
class PatientAdmin(UserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "is_staff",
        "is_active",
    )
    search_fields = ("username", "first_name", "last_name", "email")
    list_filter = ("is_staff", "is_active", "date_joined")


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(ModelAdmin):
    list_display = ("service", "starts_at", "ends_at", "is_booked")
    list_filter = ("service", "is_booked", "starts_at")
    search_fields = ("service__name",)
    readonly_fields = ("is_booked",)
    date_hierarchy = "starts_at"


@admin.register(Appointment)
class AppointmentAdmin(ModelAdmin):
    list_display = (
        "patient",
        "service_name",
        "starts_at",
        "assigned_clinician",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "slot__service",
        "assigned_clinician",
        "slot__starts_at",
    )
    search_fields = (
        "patient__username",
        "patient__first_name",
        "patient__last_name",
        "patient__email",
    )
    readonly_fields = (
        "patient",
        "slot",
        "active_slot",
        "status",
        "created_at",
        "reminder_sent_at",
    )
    actions = ("cancel_upcoming_appointments", "mark_as_completed")
    date_hierarchy = "slot__starts_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Service")
    def service_name(self, obj: Appointment) -> str:
        return obj.slot.service.name

    @admin.display(description="Appointment time")
    def starts_at(self, obj: Appointment):
        return obj.slot.starts_at

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_clinician":
            kwargs["queryset"] = Clinician.objects.filter(is_active=True).select_related(
                "user"
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change) -> None:
        previous_clinician_id = None
        if change:
            previous_clinician_id = (
                Appointment.objects.filter(pk=obj.pk)
                .values_list("assigned_clinician_id", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if (
            obj.assigned_clinician_id
            and obj.assigned_clinician_id != previous_clinician_id
        ):
            if not send_appointment_notification(obj, "assigned"):
                self.message_user(
                    request,
                    "The assignment was saved, but its email notification could not be sent.",
                    messages.WARNING,
                )

    @admin.action(description="Cancel selected upcoming appointments")
    def cancel_upcoming_appointments(self, request, queryset) -> None:
        cancelled = 0
        email_failures = 0
        for appointment_id in queryset.values_list("pk", flat=True):
            try:
                appointment = cancel_appointment(appointment_id=appointment_id)
            except (Appointment.DoesNotExist, AppointmentError):
                continue
            cancelled += 1
            if not send_appointment_notification(appointment, "cancelled"):
                email_failures += 1
        skipped = queryset.count() - cancelled
        self.message_user(
            request,
            f"Cancelled {cancelled} upcoming appointment(s); skipped {skipped}.",
            messages.SUCCESS,
        )
        if email_failures:
            self.message_user(
                request,
                f"Email notifications could not be sent for {email_failures} cancellation(s).",
                messages.WARNING,
            )

    @admin.action(description="Mark selected past appointments as completed")
    def mark_as_completed(self, request, queryset) -> None:
        appointments = queryset.filter(
            status=Appointment.Status.SCHEDULED,
            slot__starts_at__lte=timezone.now(),
        )
        slot_ids = list(appointments.values_list("slot_id", flat=True))
        updated = appointments.update(
            status=Appointment.Status.COMPLETED,
            active_slot=None,
        )
        AppointmentSlot.objects.filter(pk__in=slot_ids).update(is_booked=False)
        self.message_user(
            request,
            f"Marked {updated} past appointment(s) as completed.",
            messages.SUCCESS,
        )
