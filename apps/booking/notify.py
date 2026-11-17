from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.notifications import sms


def confirmation_text(booking) -> str:
    start = timezone.localtime(booking.start)
    cancel_url = settings.SITE_URL + reverse("web:cancel_booking", args=[booking.cancel_token])
    return (f"{booking.workshop.name}: rezerwacja {booking.service.name} {start:%d.%m %H:%M}, "
            f"{booking.workshop.address}. Anulowanie: {cancel_url}")


def booking_confirmed(booking) -> None:
    transaction.on_commit(lambda: sms.send_sms(booking.customer.phone, confirmation_text(booking),
                                               workshop=booking.workshop, kind="booking_confirmation"))
