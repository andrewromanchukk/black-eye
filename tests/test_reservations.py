"""reservations: the single path for online and manual bookings (+ notifications)."""
from django.test import TestCase, override_settings

from apps.booking import reservations
from apps.booking.engine import SlotUnavailable
from apps.booking.models import Booking
from apps.notifications import sms

from .factories import NOW, at, make_workshop

DETAILS = reservations.CustomerDetails(name="Jan", phone="600 123 456", plate="wwl 1")


@override_settings(SMS_BACKEND="apps.notifications.backends.LocMemSmsBackend")
class ReservationsTests(TestCase):
    def setUp(self):
        sms.outbox.clear()
        self.ws, self.service = make_workshop()

    def test_online_reservation_requires_consent(self):
        with self.assertRaises(reservations.ConsentRequired):
            reservations.reserve_online(self.ws, self.service, at(10), DETAILS, consent=False, now=NOW)
        self.assertFalse(Booking.objects.exists())

    def test_online_reservation_books_and_sends_confirmation_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            b = reservations.reserve_online(self.ws, self.service, at(10), DETAILS, consent=True, now=NOW)
        self.assertEqual(b.source, Booking.Source.ONLINE)
        self.assertEqual(len(sms.outbox), 1)
        self.assertIn(b.cancel_token, sms.outbox[0][1])

    def test_online_reservation_respects_rules(self):
        with self.assertRaises(SlotUnavailable):
            reservations.reserve_online(self.ws, self.service, at(19), DETAILS, consent=True, now=NOW)

    def test_manual_reservation_skips_hours_and_sends_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            b = reservations.reserve_manual(self.ws, self.service, at(19), DETAILS)
        self.assertEqual(b.source, Booking.Source.MANUAL)
        self.assertEqual(sms.outbox, [])

    def test_cancel_by_customer(self):
        b = reservations.reserve_online(self.ws, self.service, at(10), DETAILS, consent=True, now=NOW)
        reservations.cancel_by_customer(b, now=NOW)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.Status.CANCELLED)
        with self.assertRaises(reservations.CannotCancel):
            reservations.cancel_by_customer(b, now=NOW)
