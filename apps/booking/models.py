import re
import secrets

from django.db import models

from apps.workshops.models import Bay, Service, Workshop


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("48") and len(digits) == 11:
        digits = digits[2:]
    return digits


def normalize_plate(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def new_cancel_token() -> str:
    return secrets.token_urlsafe(24)


class Customer(models.Model):
    """A driver, identified within a Workshop by phone number. No account."""

    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField("Imię", max_length=120)
    phone = models.CharField("Telefon", max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workshop", "phone"], name="uniq_customer_phone")]

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Potwierdzona"
        COMPLETED = "completed", "Wykonana"
        NO_SHOW = "no_show", "Nie przyszedł"
        CANCELLED = "cancelled", "Anulowana"

    class Source(models.TextChoices):
        ONLINE = "online", "Online"
        MANUAL = "manual", "Telefon / ręcznie"

    # Statuses that occupy the bay's time.
    BLOCKING = (Status.CONFIRMED, Status.COMPLETED)

    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="bookings")
    bay = models.ForeignKey(Bay, on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="bookings")
    plate = models.CharField("Nr rejestracyjny", max_length=16)
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.ONLINE)
    note = models.CharField("Uwagi", max_length=300, blank=True)
    cancel_token = models.CharField(max_length=64, unique=True, default=new_cancel_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start"]
        indexes = [models.Index(fields=["bay", "start"]), models.Index(fields=["workshop", "start"])]
        constraints = [models.CheckConstraint(condition=models.Q(end__gt=models.F("start")), name="booking_end_after_start")]

    def __str__(self):
        return f"{self.service} · {self.start:%Y-%m-%d %H:%M} · {self.bay}"
