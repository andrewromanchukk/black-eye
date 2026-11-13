from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.forms import inlineformset_factory

from apps.storage.models import TireDeposit
from apps.workshops.models import Bay, OpeningHours, Service, Workshop

User = get_user_model()


class KitMixin:
    """Apply kit.css classes to widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            css = "select" if isinstance(w, forms.Select) else "textarea" if isinstance(w, forms.Textarea) else "input"
            w.attrs.setdefault("class", css)


class SignupForm(KitMixin, forms.Form):
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(label="Hasło", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                               help_text="Min. 8 znaków, nie same cyfry.")
    workshop_name = forms.CharField(label="Nazwa warsztatu", max_length=120)
    address = forms.CharField(label="Adres", max_length=200)
    phone = forms.CharField(label="Telefon warsztatu", max_length=20,
                            widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}))
    accept_terms = forms.BooleanField(label="Akceptuję regulamin i politykę prywatności")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Konto z tym adresem już istnieje.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password") and data.get("email"):
            validate_password(data["password"], User(username=data["email"], email=data["email"]))
        return data


class WorkshopForm(KitMixin, forms.ModelForm):
    class Meta:
        model = Workshop
        fields = ["name", "slug", "address", "phone", "slot_step_min", "booking_horizon_days", "min_notice_min",
                  "visit_reminders"]


class OpeningHoursForm(KitMixin, forms.ModelForm):
    class Meta:
        model = OpeningHours
        fields = ["is_closed", "opens", "closes"]
        widgets = {"opens": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "closes": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}

    def clean(self):
        data = super().clean()
        if not data.get("is_closed"):
            if not data.get("opens") or not data.get("closes"):
                raise forms.ValidationError("Podaj godziny albo zaznacz „Zamknięte”.")
            if data["opens"] >= data["closes"]:
                raise forms.ValidationError("Otwarcie musi być przed zamknięciem.")
        return data


OpeningHoursFormSet = inlineformset_factory(
    Workshop, OpeningHours, form=OpeningHoursForm, extra=0, can_delete=False)


class BayForm(KitMixin, forms.ModelForm):
    class Meta:
        model = Bay
        fields = ["name", "is_active"]


class ServiceForm(KitMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "duration_min", "price", "bays", "is_active"]
        widgets = {"bays": forms.CheckboxSelectMultiple}

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bays"].queryset = workshop.bays.all()


class CustomerDetailsForm(KitMixin, forms.Form):
    name = forms.CharField(label="Imię", max_length=120, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    phone = forms.CharField(label="Telefon", max_length=20,
                            widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel"}))
    plate = forms.CharField(label="Nr rejestracyjny", max_length=16, help_text="Np. WWL 12345",
                            widget=forms.TextInput(attrs={"autocapitalize": "characters", "class": "input mono"}))
    note = forms.CharField(label="Uwagi (opcjonalnie)", max_length=300, required=False,
                           widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Np. mam swoje opony w przechowalni"}))


class PublicBookingForm(CustomerDetailsForm):
    consent = forms.BooleanField(label="Akceptuję politykę prywatności i zgadzam się na kontakt SMS w sprawie wizyty.")


class ManualBookingForm(CustomerDetailsForm):
    service = forms.ModelChoiceField(label="Usługa", queryset=Service.objects.none())
    start = forms.DateTimeField(label="Początek", input_formats=["%Y-%m-%dT%H:%M"],
                                widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))

    field_order = ["service", "start", "name", "phone", "plate", "note"]

    def __init__(self, *args, workshop, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = workshop.services.all()


class TireDepositForm(KitMixin, forms.Form):
    customer_name = forms.CharField(label="Imię klienta", max_length=120)
    phone = forms.CharField(label="Telefon", max_length=20, widget=forms.TextInput(attrs={"type": "tel"}))
    plate = forms.CharField(label="Nr rejestracyjny", max_length=16)
    season = forms.ChoiceField(label="Opony", choices=TireDeposit.Season.choices)
    description = forms.CharField(label="Opis", max_length=200, help_text="Np. 205/55 R16, Michelin, z felgami")
    location = forms.CharField(label="Miejsce w magazynie", max_length=40, required=False, help_text="Np. Regał B, półka 3")
