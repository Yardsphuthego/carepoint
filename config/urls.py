from django.contrib import admin
from django.urls import include, path

from appointments import views


urlpatterns = [
    path("health/", views.health_check, name="health"),
    path("post-login/", views.post_login, name="post_login"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("appointments.urls")),
]
