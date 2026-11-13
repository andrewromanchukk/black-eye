"""Booking engine: the seam where all availability rules live."""
from datetime import timedelta

from django.test import TestCase

from apps.booking import engine
from apps.booking.models import Booking
from apps.workshops.models import Bay, Service

from .factories import MONDAY, NOW, at, make_workshop


def book(ws, service, start, phone="600123456", **kw):
    return engine.book(ws, service, start, customer_name="Jan", phone=phone, plate="wwl 123", now=NOW, **kw)


class AvailableSlotsTests(TestCase):
    def setUp(self):
        self.ws, self.service = make_workshop()

    def labels(self, day=MONDAY, service=None, now=NOW):
        return [s.label for s in engine.available_slots(self.ws, service or self.service, day, now=now)]

    def test_slots_cover_opening_hours_with_step_and_fit_duration(self):
        labels = self.labels()
        self.assertEqual(labels[0], "08:00")
        self.assertEqual(labels[-1], "16:00")  # 60 min service must end by 17:00
        self.assertIn("08:30", labels)  # default step 30 min

    def test_closed_day_has_no_slots(self):
        sunday = MONDAY + timedelta(days=6)
        self.assertEqual(self.labels(day=sunday), [])

    def test_past_day_and_beyond_horizon_have_no_slots(self):
        self.assertEqual(self.labels(day=MONDAY - timedelta(days=7)), [])
        self.assertEqual(self.labels(day=MONDAY + timedelta(days=self.ws.booking_horizon_days + 1)), [])

    def test_min_notice_hides_too_early_slots(self):
        self.ws.min_notice_min = 120
        self.ws.save()
        self.assertEqual(self.labels(now=at(9))[0], "11:00")

    def test_booked_bay_time_is_not_offered(self):
        book(self.ws, self.service, at(10))
        labels = self.labels()
        for taken in ("09:30", "10:00", "10:30"):
            self.assertNotIn(taken, labels)
        self.assertIn("09:00", labels)
        self.assertIn("11:00", labels)

    def test_second_bay_keeps_slot_open(self):
        Bay.objects.create(workshop=self.ws, name="Stanowisko 2")
        book(self.ws, self.service, at(10))
        self.assertIn("10:00", self.labels())

    def test_cancelled_booking_frees_the_slot(self):
        engine.cancel(book(self.ws, self.service, at(10)))
        self.assertIn("10:00", self.labels())

    def test_inactive_bay_gets_no_slots(self):
        self.ws.bays.update(is_active=False)
        self.assertEqual(self.labels(), [])

    def test_service_restricted_to_specific_bay(self):
        lift = Bay.objects.create(workshop=self.ws, name="Podnośnik")
        oil = Service.objects.create(workshop=self.ws, name="Wymiana oleju", duration_min=30)
        oil.bays.add(lift)
        booking = book(self.ws, oil, at(10))
        self.assertEqual(booking.bay, lift)
        self.assertNotIn("10:00", self.labels(service=oil))
        self.assertIn("10:00", self.labels())  # tire bay still free

    def test_hidden_service_has_no_slots(self):
        self.service.is_active = False
        self.service.save()
        self.assertEqual(self.labels(), [])


class BookTests(TestCase):
    def setUp(self):
        self.ws, self.service = make_workshop()

    def test_book_creates_confirmed_booking_with_normalized_data(self):
        b = book(self.ws, self.service, at(10), phone="+48 600-123-456")
        self.assertEqual(b.status, Booking.Status.CONFIRMED)
        self.assertEqual(b.customer.phone, "600123456")
        self.assertEqual(b.plate, "WWL123")
        self.assertEqual(b.end - b.start, timedelta(minutes=60))
        self.assertTrue(b.cancel_token)

    def test_same_phone_reuses_customer(self):
        a = book(self.ws, self.service, at(8))
        b = book(self.ws, self.service, at(12))
        self.assertEqual(a.customer_id, b.customer_id)

    def test_taken_slot_raises(self):
        book(self.ws, self.service, at(10))
        with self.assertRaises(engine.SlotUnavailable):
            book(self.ws, self.service, at(10, 30), phone="600999999")

    def test_slot_outside_rules_raises(self):
        with self.assertRaises(engine.SlotUnavailable):
            book(self.ws, self.service, at(10, 10))  # not on 30-min grid
        with self.assertRaises(engine.SlotUnavailable):
            book(self.ws, self.service, at(18))  # after closing

    def test_invalid_phone_raises(self):
        with self.assertRaises(engine.InvalidBooking):
            engine.book(self.ws, self.service, at(10), customer_name="Jan", phone="12", plate="X", now=NOW)

    def test_manual_booking_ignores_hours_but_not_overlaps(self):
        late = engine.book(self.ws, self.service, at(18), customer_name="Ola", phone="600111222", plate="KR1",
                           source=Booking.Source.MANUAL, enforce_rules=False, now=NOW)
        self.assertEqual(late.source, Booking.Source.MANUAL)
        with self.assertRaises(engine.SlotUnavailable):
            engine.book(self.ws, self.service, at(18, 30), customer_name="Ola", phone="600111222", plate="KR1",
                        enforce_rules=False, now=NOW)

    def test_customer_can_cancel_only_future_confirmed(self):
        b = book(self.ws, self.service, at(10))
        self.assertTrue(engine.can_customer_cancel(b, now=NOW))
        self.assertFalse(engine.can_customer_cancel(b, now=at(11)))
        engine.cancel(b)
        self.assertFalse(engine.can_customer_cancel(b, now=NOW))
