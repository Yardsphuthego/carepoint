from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("api/services/", views.public_services, name="public_services"),
    path("services/", views.service_list, name="services"),
    path("register/", views.register, name="register"),
    path(
        "register/verify/<str:uidb64>/<str:token>/",
        views.verify_email,
        name="verify_email",
    ),
    path("appointments/", views.dashboard, name="dashboard"),
    path("appointments/book/<int:service_id>/", views.book, name="book"),
    path(
        "appointments/<int:appointment_id>/cancel/",
        views.cancel,
        name="cancel_appointment",
    ),
    path(
        "appointments/<int:appointment_id>/cancel/confirm/",
        views.cancel_confirmed,
        name="confirm_cancel_appointment",
    ),
    path(
        "appointments/<int:appointment_id>/reschedule/",
        views.reschedule,
        name="reschedule_appointment",
    ),
    path(
        "clinician/appointments/",
        views.clinician_dashboard,
        name="clinician_dashboard",
    ),
    path(
        "clinician/appointments/<int:appointment_id>/complete/",
        views.clinician_complete_appointment,
        name="clinician_complete_appointment",
    ),
]
