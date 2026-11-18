"""Two customers race for the last free bay: exactly one wins (PostgreSQL row locks)."""
import threading
from datetime import timedelta
import unittest

from django.db import connection
from django.test import TransactionTestCase

from apps.booking import engine
from apps.booking.models import Booking

from .factories import make_workshop
from .test_web import first_free_slot


@unittest.skipUnless(connection.vendor == "postgresql", "needs PostgreSQL row locking")
class DoubleBookingRaceTests(TransactionTestCase):
    def test_only_one_of_parallel_bookings_succeeds(self):
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        results, barrier = [], threading.Barrier(4)

        def attempt(i):
            barrier.wait()
            try:
                engine.book(ws, service, slot.start, customer_name=f"K{i}", phone=f"60000000{i}", plate=f"P{i}")
                results.append("ok")
            except engine.SlotUnavailable:
                results.append("taken")
            finally:
                connection.close()

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), ["ok", "taken", "taken", "taken"])
        self.assertEqual(Booking.objects.count(), 1)


def race(*attempts):
    """Run callables at the same moment in separate threads/connections. Returns 'ok'/'taken' per attempt."""
    results, barrier = [None] * len(attempts), threading.Barrier(len(attempts))

    def run(i, fn):
        barrier.wait()
        try:
            fn()
            results[i] = "ok"
        except engine.SlotUnavailable:
            results[i] = "taken"
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@unittest.skipUnless(connection.vendor == "postgresql", "needs PostgreSQL row locking")
class MoreBookingRaceTests(TransactionTestCase):
    def book(self, ws, service, start, i, **kw):
        return lambda: engine.book(ws, service, start, customer_name=f"K{i}", phone=f"60000000{i}", plate=f"P{i}",
                                   **kw)

    def test_two_bays_take_two_of_three_parallel_bookings(self):
        ws, service = make_workshop(bays=2)
        slot = first_free_slot(ws, service)
        results = race(*(self.book(ws, service, slot.start, i) for i in range(3)))
        self.assertEqual(sorted(results), ["ok", "ok", "taken"])
        self.assertEqual(set(Booking.objects.values_list("bay_id", flat=True)), set(ws.bays.values_list("pk", flat=True)))

    def test_overlapping_bookings_with_different_starts_cannot_both_win(self):
        ws, service = make_workshop()  # one bay, 60 min service, 30 min step
        slot = first_free_slot(ws, service)
        results = race(self.book(ws, service, slot.start, 1),
                       self.book(ws, service, slot.start + timedelta(minutes=30), 2))
        self.assertEqual(sorted(results), ["ok", "taken"])
        self.assertEqual(Booking.objects.count(), 1)

    def test_manual_booking_and_online_booking_race_for_one_bay(self):
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        results = race(self.book(ws, service, slot.start, 1),
                       self.book(ws, service, slot.start, 2, source=Booking.Source.MANUAL, enforce_rules=False))
        self.assertEqual(sorted(results), ["ok", "taken"])
        self.assertEqual(Booking.objects.count(), 1)
