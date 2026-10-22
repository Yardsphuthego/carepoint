from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import AppointmentSlot


class PatientRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email


class SlotSelectionForm(forms.Form):
    slot = forms.ModelChoiceField(
        queryset=AppointmentSlot.objects.none(),
        empty_label="Choose an available time",
        label="Available time",
    )

    def __init__(self, *args, service_id: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["slot"].queryset = AppointmentSlot.objects.filter(
            service_id=service_id,
            service__is_active=True,
            is_booked=False,
            starts_at__gt=timezone.now(),
        ).select_related("service")

    def clean_slot(self) -> AppointmentSlot:
        slot = self.cleaned_data["slot"]
        if slot.starts_at <= timezone.now() or slot.is_booked:
            raise forms.ValidationError("That time is no longer available.")
        return slot
