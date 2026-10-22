from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from appointments.models import Appointment, AppointmentSlot, Clinician, Service


class Command(BaseCommand):
    help = "Create the built-in clinic administrator and booking coordinator groups."

    def handle(self, *args, **options) -> None:
        models_by_app = {
            "appointments": (Service, AppointmentSlot, Appointment, Clinician),
            "users": (get_user_model(),),
        }
        manager_permissions = []
        coordinator_permissions = []
        for app_models in models_by_app.values():
            for model in app_models:
                content_type = ContentType.objects.get_for_model(model)
                permissions = Permission.objects.filter(content_type=content_type)
                manager_permissions.extend(permissions)
                model_name = model._meta.model_name
                if model in (Service, AppointmentSlot):
                    coordinator_permissions.extend(
                        permissions.filter(
                            codename__in=(
                                f"view_{model_name}",
                                f"add_{model_name}",
                                f"change_{model_name}",
                            )
                        )
                    )
                elif model in (Appointment, Clinician):
                    coordinator_permissions.extend(
                        permissions.filter(
                            codename__in=(
                                f"view_{model_name}",
                                f"change_{model_name}",
                            )
                        )
                    )

        clinic_admin, _ = Group.objects.get_or_create(name="Clinic administrators")
        clinic_admin.permissions.set(manager_permissions)
        coordinator, _ = Group.objects.get_or_create(name="Booking coordinators")
        coordinator.permissions.set(coordinator_permissions)
        self.stdout.write(
            self.style.SUCCESS(
                "Clinic administrators and Booking coordinators roles are ready."
            )
        )
