"""Reservations — the one module that turns a request into a Booking.

Web views, REST API and (later) the mobile app call only this module. It owns
the rules around the Booking engine: customer consent and notifications.

    reserve_online(workshop, service, start, details, *, consent) -> Booking
    reserve_manual(workshop, service, start, details) -> Booking
    cancel_by_customer(booking) -> Booking

Errors: engine.SlotUnavailable, engine.InvalidBooking, ConsentRequired, CannotCancel.
"""
from dataclasses import dataclass
from datetime import datetime

from . import engine, notify
from .models import Booking


class ConsentRequired(engine.InvalidBooking):
    """The customer did not accept the privacy policy."""


class CannotCancel(Exception):
    """The booking is in the past or no longer confirmed."""


@dataclass(frozen=True)
class CustomerDetails:
    name: str
    phone: str
    plate: str
    note: str = ""


def _book(workshop, service, start, details: CustomerDetails, **kw) -> Booking:
    return engine.book(workshop, service, start, customer_name=details.name, phone=details.phone,
                       plate=details.plate, note=details.note, **kw)


def reserve_online(workshop, service, start: datetime, details: CustomerDetails, *, consent: bool,
                   now: datetime | None = None) -> Booking:
    """Customer self-booking: all availability rules apply; confirmation SMS goes out after commit."""
    if not consent:
        raise ConsentRequired("Zaakceptuj politykę prywatności, aby zarezerwować wizytę.")
    booking = _book(workshop, service, start, details, source=Booking.Source.ONLINE, now=now)
    notify.booking_confirmed(booking)
    return booking


def reserve_manual(workshop, service, start: datetime, details: CustomerDetails) -> Booking:
    """Owner books a phone call: opening hours are not enforced, overlaps on a bay still are."""
    return _book(workshop, service, start, details, source=Booking.Source.MANUAL, enforce_rules=False)


def cancel_by_customer(booking: Booking, now: datetime | None = None) -> Booking:
    if not engine.can_customer_cancel(booking, now=now):
        raise CannotCancel("Tej rezerwacji nie można już anulować.")
    return engine.cancel(booking)
