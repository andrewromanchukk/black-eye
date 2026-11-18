from django.test import TestCase

from apps.booking import customers, engine
from apps.booking.models import Booking, Customer
from apps.storage import services as storage

from .factories import NOW, at, make_workshop


class CustomersTests(TestCase):
    def setUp(self):
        self.ws, self.service = make_workshop()

    def test_booking_and_deposit_with_same_phone_share_one_customer_with_latest_name(self):
        engine.book(self.ws, self.service, at(10), customer_name="Jan", phone="600 123 456", plate="WWL1", now=NOW)
        storage.register_deposit(self.ws, customer_name="Jan Kowalski", phone="+48600123456", plate="WWL1",
                                 season="winter", description="195/65 R15")
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.get().name, "Jan Kowalski")

    def test_same_phone_in_another_workshop_is_another_customer(self):
        other, _ = make_workshop("other@example.com")
        customers.resolve(self.ws, "Jan", "600123456")
        customers.resolve(other, "Jan", "600123456")
        self.assertEqual(Customer.objects.count(), 2)

    def test_search_by_name_phone_and_plate(self):
        engine.book(self.ws, self.service, at(10), customer_name="Anna", phone="501222333", plate="WX7788K", now=NOW)
        storage.register_deposit(self.ws, customer_name="Piotr", phone="602444555", plate="KR1234",
                                 season="summer", description="x")
        names = lambda q: [c.name for c in customers.search(self.ws, q)]
        self.assertEqual(names("ann"), ["Anna"])
        self.assertEqual(names("501 222"), ["Anna"])
        self.assertEqual(names("wx 7788"), ["Anna"])
        self.assertEqual(names("kr12"), ["Piotr"])
        self.assertEqual(len(names("")), 2)

    def test_history_counts_visits_and_lists_cars_and_tires(self):
        b1 = engine.book(self.ws, self.service, at(8), customer_name="Jan", phone="600123456", plate="AAA1", now=NOW)
        b2 = engine.book(self.ws, self.service, at(10), customer_name="Jan", phone="600123456", plate="BBB2", now=NOW)
        engine.set_status(b1, Booking.Status.COMPLETED)
        engine.set_status(b2, Booking.Status.NO_SHOW)
        storage.register_deposit(self.ws, customer_name="Jan", phone="600123456", plate="AAA1", season="winter",
                                 description="z felgami")
        h = customers.history(b1.customer)
        self.assertEqual(h.plates, ["AAA1", "BBB2"])
        self.assertEqual((h.visits_done, h.no_shows), (1, 1))
        self.assertEqual([b.pk for b in h.bookings], [b2.pk, b1.pk])
        self.assertEqual(len(h.deposits), 1)


class StorageSearchTests(TestCase):
    def test_plate_query_does_not_match_digits_inside_phone(self):
        ws, _ = make_workshop()
        storage.register_deposit(ws, customer_name="Anna", phone="501222333", plate="WX7788K", season="summer",
                                 description="x")
        storage.register_deposit(ws, customer_name="Piotr", phone="602444555", plate="KR1234", season="summer",
                                 description="x")
        self.assertEqual([d.plate for d in storage.search(ws, "kr12")], ["KR1234"])
        self.assertEqual([d.plate for d in storage.search(ws, "501 222")], ["WX7788K"])


class CustomerSearchEdgeCasesTests(TestCase):
    def setUp(self):
        self.ws, self.service = make_workshop()
        engine.book(self.ws, self.service, at(8), customer_name="Łukasz Żółć", phone="501222333", plate="WX7788K",
                    now=NOW)
        engine.book(self.ws, self.service, at(10), customer_name="Łukasz Żółć", phone="501222333", plate="WX7788K",
                    now=NOW)
        engine.book(self.ws, self.service, at(12), customer_name="Ola", phone="698111000", plate="KR4P123", now=NOW)

    def names(self, q):
        return [c.name for c in customers.search(self.ws, q)]

    def test_name_is_case_insensitive_with_polish_letters(self):
        self.assertEqual(self.names("łukasz"), ["Łukasz Żółć"])
        self.assertEqual(self.names("ŻÓŁĆ"), ["Łukasz Żółć"])

    def test_phone_in_any_format(self):
        for q in ("+48 501 222 333", "48501222333", "501-222-333", "222 333"):
            with self.subTest(q=q):
                self.assertEqual(self.names(q), ["Łukasz Żółć"])

    def test_too_short_digit_query_does_not_match_phones(self):
        self.assertEqual(self.names("50"), [])

    def test_plate_lowercase_with_spaces(self):
        self.assertEqual(self.names("kr 4p"), ["Ola"])
        self.assertEqual(self.names("wx 7788 k"), ["Łukasz Żółć"])

    def test_customer_with_many_bookings_is_listed_once(self):
        self.assertEqual(self.names("WX7788K"), ["Łukasz Żółć"])

    def test_blank_query_returns_everyone(self):
        self.assertCountEqual(self.names("   "), ["Ola", "Łukasz Żółć"])

    def test_no_match(self):
        self.assertEqual(self.names("Zenon"), [])
