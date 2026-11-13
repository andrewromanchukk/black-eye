"""Booking engine — the only place where availability rules live.

Interface (used by web views, REST API and the owner's manual booking):

    available_slots(workshop, service, day, now=None) -> list[Slot]
    book(workshop, service, start, customer_name, phone, plate, note="", source="online", now=None) -> Booking
    cancel(booking) / set_status(booking, status)

`book` re-checks availability inside a transaction while holding row locks on the
workshop's bays, so two concurrent requests can never take the same bay time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.workshops.models import Bay, Service, Workshop

from .models import Booking, Customer, normalize_phone, normalize_plate

WARSAW = ZoneInfo("Europe/Warsaw")


class SlotUnavailable(Exception):
    """The requested start time is no longer (or never was) bookable."""


class InvalidBooking(ValueError):
    """Input data is not acceptable (e.g. empty phone)."""


@dataclass(frozen=True)
class Slot:
    start: datetime  # aware, Europe/Warsaw
    end: datetime
    free_bays: tuple[int, ...]

    @property
    def label(self) -> str:
        return self.start.strftime("%H:%M")


def _candidate_bays(service: Service) -> list[Bay]:
    """Active bays that can serve `service`. No explicit bays on the service = every bay of the workshop."""
    source = service.bays if service.bays.exists() else service.workshop.bays
    return list(source.filter(is_active=True).order_by("position", "pk"))


def _busy_intervals(bay_ids, start: datetime, end: datetime) -> dict[int, list[tuple[datetime, datetime]]]:
    busy: dict[int, list[tuple[datetime, datetime]]] = {b: [] for b in bay_ids}
    rows = Booking.objects.filter(
        bay_id__in=bay_ids, status__in=Booking.BLOCKING, start__lt=end, end__gt=start
    ).values_list("bay_id", "start", "end")
    for bay_id, s, e in rows:
        busy[bay_id].append((s, e))
    return busy


def _is_free(intervals, start: datetime, end: datetime) -> bool:
    return all(not (start < e and end > s) for s, e in intervals)


def _bookable_window(workshop: Workshop, day: date, now: datetime) -> tuple[datetime, datetime] | None:
    """Opening window of `day` in local time, or None if the day is not bookable at all."""
    today = now.astimezone(WARSAW).date()
    if day < today or day > today + timedelta(days=workshop.booking_horizon_days):
        return None
    hours = workshop.opening_hours.filter(weekday=day.weekday()).first()
    if not hours or hours.is_closed or not hours.opens or not hours.closes or hours.opens >= hours.closes:
        return None
    return (datetime.combine(day, hours.opens, tzinfo=WARSAW), datetime.combine(day, hours.closes, tzinfo=WARSAW))


def available_slots(workshop: Workshop, service: Service, day: date, now: datetime | None = None) -> list[Slot]:
    now = now or timezone.now()
    if not service.is_active or service.workshop_id != workshop.pk:
        return []
    window = _bookable_window(workshop, day, now)
    if window is None:
        return []
    opens, closes = window
    bays = _candidate_bays(service)
    if not bays:
        return []
    duration = timedelta(minutes=service.duration_min)
    step = timedelta(minutes=workshop.slot_step_min)
    earliest = now + timedelta(minutes=workshop.min_notice_min)
    busy = _busy_intervals([b.pk for b in bays], opens, closes)

    slots: list[Slot] = []
    start = opens
    while start + duration <= closes:
        end = start + duration
        if start >= earliest:
            free = tuple(b.pk for b in bays if _is_free(busy[b.pk], start, end))
            if free:
                slots.append(Slot(start=start, end=end, free_bays=free))
        start += step
    return slots


def find_slot(workshop: Workshop, service: Service, start: datetime, now: datetime | None = None) -> Slot | None:
    start = start.astimezone(WARSAW)
    for slot in available_slots(workshop, service, start.date(), now=now):
        if slot.start == start:
            return slot
    return None


def book(workshop: Workshop, service: Service, start: datetime, *, customer_name: str, phone: str, plate: str,
         note: str = "", source: str = Booking.Source.ONLINE, now: datetime | None = None,
         enforce_rules: bool = True) -> Booking:
    """Reserve `start` for `service`. Picks the first free bay. Raises SlotUnavailable / InvalidBooking.

    enforce_rules=False (owner's manual booking) skips opening hours, step and notice rules,
    but never allows overlapping another booking on the same bay.
    """
    phone_n, plate_n, name = normalize_phone(phone), normalize_plate(plate), (customer_name or "").strip()
    if len(phone_n) < 9:
        raise InvalidBooking("Podaj poprawny numer telefonu.")
    if not plate_n:
        raise InvalidBooking("Podaj numer rejestracyjny.")
    if not name:
        raise InvalidBooking("Podaj imię.")
    if timezone.is_naive(start):
        start = start.replace(tzinfo=WARSAW)
    end = start + timedelta(minutes=service.duration_min)

    with transaction.atomic():
        # Serialize bookings per workshop: lock all its bays.
        bays = list(Bay.objects.select_for_update().filter(workshop=workshop).order_by("pk"))
        if enforce_rules:
            slot = find_slot(workshop, service, start, now=now)
            if slot is None:
                raise SlotUnavailable("Ten termin jest już zajęty.")
            bay_ids = list(slot.free_bays)
        else:
            candidates = {b.pk for b in _candidate_bays(service)}
            bay_ids = [b.pk for b in bays if b.pk in candidates]
            busy = _busy_intervals(bay_ids, start, end)
            bay_ids = [b for b in bay_ids if _is_free(busy[b], start, end)]
            if not bay_ids:
                raise SlotUnavailable("Wszystkie stanowiska są zajęte w tym czasie.")

        customer, _ = Customer.objects.get_or_create(workshop=workshop, phone=phone_n, defaults={"name": name})
        if customer.name != name:
            customer.name = name
            customer.save(update_fields=["name"])
        return Booking.objects.create(
            workshop=workshop, bay_id=bay_ids[0], service=service, customer=customer, plate=plate_n,
            start=start, end=end, note=(note or "").strip()[:300], source=source,
        )


def can_customer_cancel(booking: Booking, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return booking.status == Booking.Status.CONFIRMED and booking.start > now


def set_status(booking: Booking, status: str) -> Booking:
    if status not in Booking.Status.values:
        raise InvalidBooking("Nieznany status.")
    booking.status = status
    booking.save(update_fields=["status"])
    return booking


def cancel(booking: Booking) -> Booking:
    return set_status(booking, Booking.Status.CANCELLED)


def bookable_days(workshop: Workshop, now: datetime | None = None, limit: int = 14) -> list[date]:
    """Next days on which the workshop is open (for the date strip)."""
    now = now or timezone.now()
    today = now.astimezone(WARSAW).date()
    open_weekdays = set(workshop.opening_hours.filter(is_closed=False).values_list("weekday", flat=True))
    days, d = [], today
    while len(days) < limit and d <= today + timedelta(days=workshop.booking_horizon_days):
        if d.weekday() in open_weekdays:
            days.append(d)
        d += timedelta(days=1)
    return days
