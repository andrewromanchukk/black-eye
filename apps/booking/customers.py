"""Customers: one Customer per phone number within a Workshop.

    resolve(workshop, name, phone) -> Customer   create or update name (latest wins)
    search(workshop, q) -> QuerySet[Customer]    by name, phone or plate
    history(customer) -> CustomerHistory         visits, cars, tire sets
"""
from dataclasses import dataclass

from django.db.models import Q, QuerySet

from .models import Booking, Customer, normalize_phone, normalize_plate


def resolve(workshop, name: str, phone: str) -> Customer:
    phone_n, name = normalize_phone(phone), (name or "").strip()
    customer, created = Customer.objects.get_or_create(workshop=workshop, phone=phone_n, defaults={"name": name})
    if not created and name and customer.name != name:
        customer.name = name
        customer.save(update_fields=["name"])
    return customer


def search(workshop, q: str = "") -> QuerySet:
    qs = Customer.objects.filter(workshop=workshop)
    q = (q or "").strip()
    if q:
        cond = Q(name__icontains=q)
        looks_like_phone = not any(ch.isalpha() for ch in q)
        if looks_like_phone and len(phone := normalize_phone(q)) >= 3:
            cond |= Q(phone__contains=phone)
        if plate := normalize_plate(q):
            cond |= Q(bookings__plate__contains=plate) | Q(tire_deposits__plate__contains=plate)
        qs = qs.filter(cond).distinct()
    return qs.order_by("name", "pk")


@dataclass
class CustomerHistory:
    customer: Customer
    bookings: list
    deposits: list
    plates: list[str]
    visits_done: int
    no_shows: int


def history(customer: Customer) -> CustomerHistory:
    bookings = list(customer.bookings.select_related("service", "bay").order_by("-start"))
    deposits = list(customer.tire_deposits.order_by("-stored_at", "-pk"))
    plates = sorted({b.plate for b in bookings} | {d.plate for d in deposits})
    return CustomerHistory(
        customer=customer, bookings=bookings, deposits=deposits, plates=plates,
        visits_done=sum(b.status == Booking.Status.COMPLETED for b in bookings),
        no_shows=sum(b.status == Booking.Status.NO_SHOW for b in bookings),
    )
