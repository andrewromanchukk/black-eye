"""Tire storage operations: register, return, season reminders."""
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.booking import customers
from apps.booking.models import normalize_phone, normalize_plate
from apps.notifications import sms

from .models import TireDeposit


def register_deposit(workshop, *, customer_name, phone, plate, season, description, location="", stored_at=None):
    customer = customers.resolve(workshop, customer_name, phone)
    return TireDeposit.objects.create(
        workshop=workshop, customer=customer, plate=normalize_plate(plate), season=season,
        description=description, location=location, stored_at=stored_at or date.today(),
    )


def mark_returned(deposit: TireDeposit) -> TireDeposit:
    deposit.status = TireDeposit.Status.RETURNED
    deposit.returned_at = date.today()
    deposit.save(update_fields=["status", "returned_at"])
    return deposit


def search(workshop, query: str = "", status: str | None = TireDeposit.Status.STORED):
    qs = TireDeposit.objects.filter(workshop=workshop).select_related("customer")
    if status:
        qs = qs.filter(status=status)
    query = (query or "").strip()
    if query:
        cond = Q(customer__name__icontains=query)
        if plate := normalize_plate(query):
            cond |= Q(plate__contains=plate)
        if not any(ch.isalpha() for ch in query) and len(phone := normalize_phone(query)) >= 3:
            cond |= Q(customer__phone__contains=phone)
        qs = qs.filter(cond)
    return qs


def reminder_candidates(workshop, season: str):
    """Stored sets of `season` — their owners should come to swap them."""
    return search(workshop, status=TireDeposit.Status.STORED).filter(season=season)


def reminder_text(workshop, deposit: TireDeposit) -> str:
    url = settings.SITE_URL + reverse("web:public_booking", args=[workshop.slug])
    return (f"{workshop.name}: czas na wymianę opon! Twoje opony ({deposit.plate}) czekają w przechowalni. "
            f"Zarezerwuj termin: {url}")


@transaction.atomic
def send_reminders(workshop, deposit_ids) -> int:
    sent = 0
    deposits = TireDeposit.objects.filter(
        workshop=workshop, pk__in=deposit_ids, status=TireDeposit.Status.STORED).select_related("customer")
    for deposit in deposits:
        sms.send_sms(deposit.customer.phone, reminder_text(workshop, deposit))
        deposit.reminded_at = timezone.now()
        deposit.save(update_fields=["reminded_at"])
        sent += 1
    return sent
