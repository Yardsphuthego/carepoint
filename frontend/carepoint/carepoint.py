"""Carepoint's presentation layer. Booking remains in the Django application."""
import os
from dataclasses import dataclass
import reflex as rx
import httpx
from reflex_components_core.el.elements.forms import Button
from reflex_base.event import EventHandler, key_event
from reflex_base.components.component import field


class CarouselButton(Button):
    on_key_down: EventHandler[key_event] = field(doc="Navigate carousel with arrow keys")


BOOKING_URL = os.environ.get("CAREPOINT_BOOKING_URL", "http://localhost:8000").rstrip("/")

API_INTERNAL_URL = os.environ.get("CAREPOINT_API_INTERNAL_URL", BOOKING_URL).rstrip("/")

def link(label, href, class_name=""):
    if href == "/book":
        return rx.el.a(label, href="#appointments", class_name=class_name,
                       on_click=BookingState.show_services)
    if href.startswith(BOOKING_URL) and any(part in href for part in ["/accounts/", "/register/", "/appointments/"]) and "/clinician/" not in href:
        return rx.el.button(label, type="button", class_name="account-trigger " + class_name,
                            on_click=BookingState.open_frame(href))
    return rx.el.a(label, href=href, class_name=class_name)


def logo():
    return rx.el.a(rx.el.span("Carepoint", class_name="wordmark"), rx.el.span("Care that fits your life.", class_name="brand-tagline"), href="/", class_name="logo", aria_label="Carepoint home")


def feature(icon, title, copy, label, href):
    return rx.el.article(rx.icon(icon, size=38, stroke_width=1.4), rx.el.h2(title), rx.el.p(copy), link(label, href, "outline-button"), class_name="feature")


def step(number, title, copy):
    return rx.el.article(rx.el.span(number, class_name="step-number"), rx.el.h3(title), rx.el.p(copy), class_name="step")


@dataclass
class ServiceItem:
    id: int
    name: str
    description: str
    duration_minutes: int


class BookingState(rx.State):
    services: list[ServiceItem] = []
    loading: bool = True
    error: str = ""
    frame_url: str = ""

    @rx.event
    def open_frame(self, url: str):
        if url.startswith(BOOKING_URL + "/"):
            self.frame_url = url

    @rx.event
    def set_modal_open(self, opened: bool):
        if not opened:
            self.frame_url = ""

    @rx.event
    def show_services(self):
        self.frame_url = ""


    @rx.event
    async def load_services(self):
        portal = self.router.url.query_parameters.get("portal", "")
        if portal.startswith(("/accounts/", "/appointments/", "/register/")) and not portal.startswith("//"):
            self.frame_url = BOOKING_URL + portal
        self.loading = True
        self.error = ""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(API_INTERNAL_URL + "/api/services/")
                response.raise_for_status()
                self.services = [ServiceItem(**item) for item in response.json()["services"]]
        except (httpx.HTTPError, ValueError, TypeError):
            self.error = "We couldn’t load appointment services. Please try again."
        finally:
            self.loading = False


def booking_card(service: ServiceItem):
    return rx.el.article(
        rx.icon("heart-pulse", size=28),
        rx.el.h2(service.name),
        rx.el.p(service.description),
        rx.el.div(rx.el.span(service.duration_minutes.to_string() + " minute appointment"),
            rx.el.button("Choose a time →", on_click=BookingState.open_frame(BOOKING_URL + "/appointments/book/" + service.id.to_string() + "/"), class_name="button"),
            class_name="booking-card-bottom"),
        class_name="booking-card",
    )


def booking_panel():
    return rx.el.section(rx.el.div(
        rx.el.p("YOUR NEXT VISIT", class_name="eyebrow"),
        rx.el.h2("Make time for your health."),
        rx.el.p("Choose a service, sign in, and manage your visit right here.", class_name="booking-intro"),
        rx.el.div(
            rx.el.button("Book an appointment", on_click=BookingState.show_services,
                         class_name=rx.cond(BookingState.frame_url == "", "portal-tab active", "portal-tab")),
            rx.el.button("Sign in", on_click=BookingState.open_frame(BOOKING_URL + "/accounts/login/"), class_name=rx.cond(BookingState.frame_url == BOOKING_URL + "/accounts/login/", "portal-tab active", "portal-tab")),
            rx.el.button("My appointments", on_click=BookingState.open_frame(BOOKING_URL + "/appointments/"), class_name=rx.cond(BookingState.frame_url == BOOKING_URL + "/appointments/", "portal-tab active", "portal-tab")),
            class_name="portal-tabs", aria_label="Appointment options",
        ),
            rx.el.div(rx.cond(BookingState.loading, rx.el.p("Loading services…"),
                rx.cond(BookingState.error != "", rx.el.div(rx.el.p(BookingState.error), rx.el.button("Try again", on_click=BookingState.load_services, class_name="button")),
                    rx.cond(BookingState.services.length() > 0,
                        rx.el.div(rx.foreach(BookingState.services, booking_card), class_name="booking-grid"),
                        rx.el.p("No services are available right now. Please check back soon.")))), aria_live="polite"),
        class_name="container booking-content"), id="appointments", class_name="booking-main")


def account_modal():
    return rx.dialog.root(
        rx.dialog.content(
            rx.el.div(
                rx.el.div(rx.dialog.title("Carepoint", class_name="account-modal-title"),
                          rx.el.span("Care that fits your life.", class_name="brand-tagline"), class_name="account-modal-brand"),
                rx.dialog.close(rx.el.button(rx.icon("x", size=20), aria_label="Close account popup", class_name="account-modal-close")),
                class_name="account-modal-header",
            ),
            rx.dialog.description("Your appointments, all in one place.", class_name="account-modal-description"),
            rx.cond(BookingState.frame_url != "", rx.el.iframe(src=BookingState.frame_url,
                    title="Carepoint patient portal", class_name="account-modal-frame")),
            class_name="account-modal",
        ),
        open=BookingState.frame_url != "",
        on_open_change=BookingState.set_modal_open,
    )


def booking():
    return rx.el.p("Opening appointments…")


HERO_SLIDES = [
    ("/doctor.jpg", "Doctor wearing a white coat and stethoscope"),
    ("/dental-room.jpeg", "A bright dental treatment room"),
    ("/hospital-lobby.jpg", "Patients and visitors in a spacious hospital lobby"),
]


class CarouselState(rx.State):
    slide: int = 0

    @rx.event
    def next_slide(self):
        self.slide = (self.slide + 1) % len(HERO_SLIDES)

    @rx.event
    def previous_slide(self):
        self.slide = (self.slide - 1) % len(HERO_SLIDES)

    @rx.event
    def select_slide(self, index: int):
        if 0 <= index < len(HERO_SLIDES):
            self.slide = index

    @rx.event
    def handle_key(self, key: str):
        if key == "ArrowRight":
            self.next_slide()
        elif key == "ArrowLeft":
            self.previous_slide()


def hero_images():
    return rx.el.div(*[
        rx.el.img(src=src, alt=alt,
            class_name=rx.cond(CarouselState.slide == i, "hero-photo carousel-photo is-active", "hero-photo carousel-photo"),
            aria_hidden=CarouselState.slide != i,
        ) for i, (src, alt) in enumerate(HERO_SLIDES)
    ], class_name="hero-images")


def carousel_controls():
    return rx.el.div(
        CarouselButton.create(rx.icon("chevron-left", size=30, stroke_width=1.5), on_key_down=CarouselState.handle_key, on_click=CarouselState.previous_slide,
                     aria_label="Previous image", class_name="carousel-arrow carousel-previous"),
        rx.el.div(*[rx.el.button(
            on_click=CarouselState.select_slide(i), aria_label=f"Show image {i + 1}: {alt}",
            aria_pressed=CarouselState.slide == i,
            class_name=rx.cond(CarouselState.slide == i, "carousel-dot is-active", "carousel-dot"),
        ) for i, (_, alt) in enumerate(HERO_SLIDES)], class_name="carousel-dots"),
        CarouselButton.create(rx.icon("chevron-right", size=30, stroke_width=1.5), on_key_down=CarouselState.handle_key, on_click=CarouselState.next_slide,
                     aria_label="Next image", class_name="carousel-arrow carousel-next"),
        rx.el.span("Image " + (CarouselState.slide + 1).to_string() + " of " + str(len(HERO_SLIDES)),
                   aria_live="polite", class_name="carousel-status"),
        class_name="carousel-controls",
    )


def index():
    return rx.el.div(
        rx.script(src="/patient-portal.js"),
        account_modal(),
        link("Skip to content", "#main", "skip-link"),
        rx.el.div(rx.el.div(rx.el.span("A little easier. A little closer. Better care."), rx.el.div(link("Patient sign in", BOOKING_URL + "/accounts/login/"), rx.el.span("/"), link("Clinician workspace", BOOKING_URL + "/clinician/appointments/"), class_name="utility-links"), class_name="container utility-inner"), class_name="utility-bar"),
        rx.el.header(rx.el.div(logo(), rx.el.nav(link("Home", "#home", "active"), link("Services", "#services"), link("About us", "#about"), link("How to book", "#how-it-works"), aria_label="Main navigation"), link("Make an appointment", "/book", "button nav-cta"), rx.el.details(rx.el.summary(rx.icon("menu"), aria_label="Open navigation"), rx.el.nav(link("Home", "#home"), link("Services", "#services"), link("About us", "#about"), link("How to book", "#how-it-works"), link("Make an appointment", "/book"), aria_label="Mobile navigation"), class_name="mobile-menu"), class_name="container header-inner")),
        rx.el.main(
            rx.el.section(hero_images(), rx.el.div(rx.el.div(rx.el.span("WELCOME TO CAREPOINT", class_name="eyebrow"), rx.el.h1(rx.el.strong("Health care"), rx.el.span("with you in mind.")), rx.el.p("A simpler way to plan your next visit. Find a service, choose your time, and take the next step in your care."), link("Explore our services", "#services", "button"), rx.el.div(rx.icon("calendar-check", size=18), rx.el.span("Your next appointment, just a few clicks away."), class_name="hero-note"), class_name="hero-copy"), class_name="container hero-inner"), carousel_controls(), id="home", class_name="hero", role="region", aria_label="Carepoint photo carousel", aria_roledescription="carousel"),
            rx.el.section(rx.el.div(feature("heart-pulse", "Care starts here", "Explore our clinic’s services and find the right appointment for your needs.", "Find a service", "/book"), feature("calendar-days", "A time that suits you", "See available appointment times and book your next visit online.", "Make an appointment", "/book"), feature("briefcase-medical", "Your visits, in one place", "View your appointments, change a booking, or plan your next visit.", "Manage appointments", BOOKING_URL + "/appointments/"), class_name="container feature-grid"), id="services", class_name="features", aria_label="Carepoint services"),
            rx.el.section(rx.el.div(rx.el.div(rx.el.img(src="/doctor.jpg", alt="A welcoming healthcare professional", loading="lazy"), rx.el.div(rx.icon("heart-handshake", size=28), rx.el.span("A simpler path", rx.el.strong("to your next visit")), class_name="image-caption"), class_name="about-image"), rx.el.div(rx.el.p("Welcome to Carepoint", class_name="section-kicker"), rx.el.h2("A little less admin.", rx.el.br(), "More room for care."), rx.el.p("Organising a clinic visit should feel straightforward. Carepoint brings services, available times, and your appointments together in one place."), rx.el.ul(*[rx.el.li(rx.icon("circle-check", size=20), text) for text in ["Browse services and available appointment times", "Book online through your patient account", "Reschedule or cancel when your plans change"]]), link("Get started", BOOKING_URL + "/register/", "button button-outline"), class_name="about-copy"), class_name="container about-grid"), id="about", class_name="about"),
            rx.el.section(rx.el.div(rx.el.p("YOUR NEXT VISIT", class_name="eyebrow"), rx.el.h2("A few simple steps. A little peace of mind."), rx.el.p("From finding a time to keeping track of your visit."), rx.el.div(step("01", "Find your service", "Browse the clinic’s services and choose the appointment you need."), step("02", "Choose your time", "Create an account, verify your email, and select an available slot."), step("03", "You're all set", "View your booking in your account and manage it whenever you need."), class_name="steps-grid"), class_name="container"), id="how-it-works", class_name="how-section"),
            rx.el.section(rx.el.div(rx.el.div(rx.el.h2("Let’s make time for your health."), rx.el.p("Your next visit starts here.")), link("Find an appointment", "/book", "button white-button"), class_name="container cta-inner"), class_name="cta-section"),
            booking_panel(),
            id="main",
        ),
        rx.el.footer(rx.el.div(rx.el.div(logo()), rx.el.div(link("Services", "/book"), link("Patient sign in", BOOKING_URL + "/accounts/login/"), link("Staff sign in", BOOKING_URL + "/admin/"), class_name="footer-links"), class_name="container footer-inner"), rx.el.div(rx.el.p("© Carepoint. All rights reserved."), rx.el.p("Appointments made simple."), class_name="container footer-bottom")),
    )


app = rx.App(stylesheets=["/carepoint.css"])
app.add_page(index, title="Carepoint | Care that fits into your day", description="Find a service, choose an appointment time, and manage your clinic visits with Carepoint.", on_load=BookingState.load_services)

app.add_page(booking, route="/book", title="Make an appointment | Carepoint", on_load=rx.redirect("/#appointments"))
