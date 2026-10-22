# Carepoint landing page

A responsive Reflex landing page inspired by the supplied Docmed reference, with Carepoint branding. Python components live in `carepoint/carepoint.py`; styling and the locally served photograph live in `assets/`.

## Run locally

Keep Django running on port 8000. In another terminal, from the repository root:

```sh
cd frontend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/reflex run
```

Open http://localhost:3000. Reflex uses port 8001 for its backend, leaving the existing Django server on 8000. The landing page links to Django's services, registration, and appointment management; it does not duplicate patient data or authentication.

For another Django address, set `CAREPOINT_BOOKING_URL` before starting Reflex. This must be an address reachable by the visitor's browser. The default is `http://localhost:8000` for local development. Django’s root URL redirects to this landing page. Set `CAREPOINT_FRONTEND_URL` on the Django server to the public Reflex URL for deployment. Service selection lives in the landing page’s appointment section and loads active services from Django’s public `/api/services/` endpoint. Legacy booking routes lead to that section. Sign-in and appointment submission use embedded Django forms.

Photograph: a stock doctor portrait from Unsplash, served locally; source: https://images.unsplash.com/photo-1612349317150-e413f6a5b16d . It is illustrative and does not identify a Carepoint clinician. Fonts are loaded from Google Fonts, with system fallbacks.

## Inline appointments and hero images

Patient links open the appointment section on the landing page. Services load from Django, and secure Django forms are embedded in that section. Use `localhost` for both servers in local development so browser session cookies remain same-site. Production should likewise use same-site HTTPS frontend and Django addresses. Django restricts patient-form framing to `CAREPOINT_FRONTEND_URL` via CSP; admin framing remains denied. Legacy `/book` links redirect to the landing page's appointment section.

The hero carousel includes the original doctor image and the supplied dental-room and hospital-lobby photos. It supports previous/next, direct slide indicators, keyboard arrows on the arrow controls, and reduced-motion preferences. It does not autoplay. The corridor image still needs a local source file.
