"""Booking engine: the seam where all availability rules live."""
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.booking import engine
from apps.booking.models import Booking
from apps.workshops.models import Bay, Service

from .factories import MONDAY, NOW, at, make_workshop

WARSAW = ZoneInfo("Europe/Warsaw")


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


class WorkingHoursAndSlotMathTests(TestCase):
    """Edge cases of opening hours and slot arithmetic."""

    def setUp(self):
        self.ws, self.service = make_workshop()

    def labels(self, day=MONDAY, service=None, now=NOW):
        return [s.label for s in engine.available_slots(self.ws, service or self.service, day, now=now)]

    def set_hours(self, weekday, opens, closes, is_closed=False):
        self.ws.opening_hours.filter(weekday=weekday).update(opens=opens, closes=closes, is_closed=is_closed)

    def test_saturday_short_day_last_slot_ends_at_closing(self):
        saturday = MONDAY + timedelta(days=5)
        labels = self.labels(day=saturday)
        self.assertEqual((labels[0], labels[-1]), ("08:00", "12:00"))  # Sat 8-13, 60 min

    def test_custom_step_and_duration(self):
        self.ws.slot_step_min = 15
        self.ws.save()
        service = Service.objects.create(workshop=self.ws, name="Wyważanie", duration_min=45)
        labels = self.labels(service=service)
        self.assertEqual(labels[:3], ["08:00", "08:15", "08:30"])
        self.assertEqual(labels[-1], "16:15")  # 16:15 + 45 min = 17:00

    def test_non_round_opening_hours(self):
        self.set_hours(MONDAY.weekday(), time(9, 15), time(12, 0))
        self.assertEqual(self.labels(), ["09:15", "09:45", "10:15", "10:45"])

    def test_service_longer_than_opening_window_has_no_slots(self):
        self.set_hours(MONDAY.weekday(), time(8), time(8, 30))
        self.assertEqual(self.labels(), [])

    def test_misconfigured_hours_open_after_close_give_no_slots(self):
        self.set_hours(MONDAY.weekday(), time(17), time(8))
        self.assertEqual(self.labels(), [])

    def test_min_notice_boundary_slot_is_offered(self):
        self.ws.min_notice_min = 60
        self.ws.save()
        self.assertEqual(self.labels(now=at(9))[0], "10:00")  # exactly now + notice

    def test_horizon_last_day_is_bookable(self):
        last = MONDAY + timedelta(days=self.ws.booking_horizon_days)
        while last.weekday() > 4:  # pick a weekday inside the horizon
            last -= timedelta(days=1)
        self.assertTrue(self.labels(day=last))

    def test_adjacent_booking_does_not_block_next_slot(self):
        book(self.ws, self.service, at(10))  # 10:00–11:00
        labels = self.labels()
        self.assertIn("09:00", labels)  # 09:00–10:00 ends exactly at 10:00
        self.assertIn("11:00", labels)

    def test_service_of_another_workshop_gets_no_slots(self):
        _, foreign = make_workshop("other@example.com")
        self.assertEqual(self.labels(service=foreign), [])

    def test_naive_start_is_treated_as_warsaw_time(self):
        b = book(self.ws, self.service, at(10).replace(tzinfo=None))
        self.assertEqual(b.start, at(10))


class DaylightSavingTests(TestCase):
    """Europe/Warsaw switches clocks on the last Sunday of March and October; slots must keep local times."""

    def setUp(self):
        self.ws, self.service = make_workshop()
        self.ws.opening_hours.filter(weekday=6).update(opens=time(8), closes=time(12), is_closed=False)

    def test_spring_forward_sunday(self):
        day = date(2026, 3, 29)
        slots = engine.available_slots(self.ws, self.service, day, now=datetime(2026, 3, 28, 7, tzinfo=WARSAW))
        self.assertEqual([s.label for s in slots][0], "08:00")
        self.assertEqual(slots[0].start.utcoffset(), timedelta(hours=2))  # CEST
        self.assertEqual(slots[0].start.astimezone(UTC).hour, 6)

    def test_fall_back_sunday_and_booking_blocks_correct_slot(self):
        day, now = date(2026, 10, 25), datetime(2026, 10, 24, 7, tzinfo=WARSAW)
        slots = engine.available_slots(self.ws, self.service, day, now=now)
        self.assertEqual(slots[0].start.utcoffset(), timedelta(hours=1))  # CET
        start = datetime(2026, 10, 25, 10, tzinfo=WARSAW)
        engine.book(self.ws, self.service, start, customer_name="Jan", phone="600123456", plate="X1", now=now)
        labels = [s.label for s in engine.available_slots(self.ws, self.service, day, now=now)]
        self.assertNotIn("10:00", labels)
        self.assertIn("09:00", labels)
        self.assertIn("11:00", labels)
