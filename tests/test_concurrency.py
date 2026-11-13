"""Two customers race for the last free bay: exactly one wins (PostgreSQL row locks)."""
import threading
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
