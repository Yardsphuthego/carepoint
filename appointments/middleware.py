"""Allow only Carepoint's frontend to embed patient forms."""
from urllib.parse import urlsplit, urlencode
from django.shortcuts import redirect, render
from django.conf import settings


class PatientFrameMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Browser navigation belongs to the Reflex shell; form submissions and
        # iframe navigation continue through Django with their session and CSRF.
        patient_entry = request.path.startswith(("/accounts/", "/appointments/book/", "/register/"))
        if (patient_entry and request.method == "GET"
                and request.headers.get("Sec-Fetch-Dest") == "document"):
            target = settings.CAREPOINT_FRONTEND_URL.rstrip("/")
            return redirect(target + "/?" + urlencode({"portal": request.get_full_path()}))
        workspace = request.path in ("/appointments/", "/admin/", "/clinician/appointments/")
        if workspace and request.user.is_authenticated and request.headers.get("Sec-Fetch-Dest") == "iframe":
            response = render(request, "appointments/open_workspace.html", {"workspace_path": request.path})
        else:
            response = self.get_response(request)
        if request.path.startswith(("/accounts/", "/appointments/", "/register/", "/post-login/")) or (workspace and request.user.is_authenticated and request.headers.get("Sec-Fetch-Dest") == "iframe"):
            frontend = urlsplit(settings.CAREPOINT_FRONTEND_URL)
            origins = {f"{frontend.scheme}://{frontend.netloc}"}
            if settings.DEBUG:
                origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
            response["Content-Security-Policy"] = "frame-ancestors 'self' " + " ".join(sorted(origins))
            response.xframe_options_exempt = True
        return response
