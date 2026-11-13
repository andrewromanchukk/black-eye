"""Visit reminders: one SMS ~24 h before a confirmed booking.

    send_visit_reminders(now=None) -> int   (run hourly; idempotent)

Window: bookings starting 20–28 h from now, so an hourly run catches each booking
several times but the reminder_sent_at marker sends it only once. A failed SMS is
retried by the next run while the booking is still in the window.
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.notifications import sms

from .models import Booking

WINDOW = (timedelta(hours=20), timedelta(hours=28))


def due(now: datetime):
    return (Booking.objects.filter(status=Booking.Status.CONFIRMED, reminder_sent_at__isnull=True,
                                   workshop__visit_reminders=True,
                                   start__gte=now + WINDOW[0], start__lt=now + WINDOW[1])
            .select_related("workshop", "service", "customer"))


def reminder_text(booking: Booking) -> str:
    start = timezone.localtime(booking.start)
    cancel_url = settings.SITE_URL + reverse("web:cancel_booking", args=[booking.cancel_token])
    return (f"{booking.workshop.name}: przypominamy o wizycie {start:%d.%m} o {start:%H:%M} "
            f"({booking.service.name}), {booking.workshop.address}. Anulowanie: {cancel_url}")


def send_visit_reminders(now: datetime | None = None) -> int:
    now = now or timezone.now()
    sent = 0
    for booking_id in list(due(now).values_list("pk", flat=True)):
        with transaction.atomic():
            booking = (due(now).select_for_update(skip_locked=True, of=("self",)).filter(pk=booking_id).first())
            if booking is None:  # taken by a parallel run or no longer due
                continue
            msg = sms.send_sms(booking.customer.phone, reminder_text(booking), workshop=booking.workshop,
                               kind="visit_reminder")
            if msg.status == msg.Status.SENT:
                booking.reminder_sent_at = now
                booking.save(update_fields=["reminder_sent_at"])
                sent += 1
    return sent
