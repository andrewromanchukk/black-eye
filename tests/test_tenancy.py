"""Tenancy: every owner route with another workshop's id answers 404."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.booking import engine
from apps.storage import services as storage
from apps.workshops import tenancy

from .factories import make_workshop
from .test_web import first_free_slot


class TenancyIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ws_a, cls.service_a = make_workshop("a@example.com")
        cls.ws_b, _ = make_workshop("b@example.com")
        slot = first_free_slot(cls.ws_a, cls.service_a)
        cls.booking = engine.book(cls.ws_a, cls.service_a, slot.start, customer_name="J", phone="600123456",
                                  plate="X1")
        cls.deposit = storage.register_deposit(cls.ws_a, customer_name="J", phone="600123456", plate="X1",
                                               season="summer", description="205/55 R16")
        cls.bay = cls.ws_a.bays.first()

    def test_web_routes_of_other_workshop_are_404(self):
        self.client.login(username="b@example.com", password="Haslo!2345")
        routes = [
            ("post", reverse("web:booking_status", args=[self.booking.pk]), {"status": "cancelled"}),
            ("get", reverse("web:bay_edit", args=[self.bay.pk]), None),
            ("post", reverse("web:bay_edit", args=[self.bay.pk]), {"name": "hack"}),
            ("get", reverse("web:service_edit", args=[self.service_a.pk]), None),
            ("post", reverse("web:storage_return", args=[self.deposit.pk]), {}),
        ]
        for method, url, data in routes:
            with self.subTest(url=url, method=method):
                r = getattr(self.client, method)(url, data or {})
                self.assertEqual(r.status_code, 404)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, "confirmed")

    def test_api_routes_of_other_workshop_are_404(self):
        client = APIClient()
        client.force_authenticate(get_user_model().objects.get(username="b@example.com"))
        routes = [
            ("get", f"/api/v1/bays/{self.bay.pk}/"), ("patch", f"/api/v1/bays/{self.bay.pk}/"),
            ("get", f"/api/v1/services/{self.service_a.pk}/"), ("delete", f"/api/v1/services/{self.service_a.pk}/"),
            ("get", f"/api/v1/bookings/{self.booking.pk}/"), ("post", f"/api/v1/bookings/{self.booking.pk}/status/"),
            ("get", f"/api/v1/tire-deposits/{self.deposit.pk}/"),
            ("post", f"/api/v1/tire-deposits/{self.deposit.pk}/return/"),
            ("get", f"/api/v1/customers/{self.booking.customer_id}/"),
        ]
        for method, url in routes:
            with self.subTest(url=url, method=method):
                r = getattr(client, method)(url, {"status": "cancelled", "name": "x"}, format="json")
                self.assertEqual(r.status_code, 404)

    def test_user_without_workshop_gets_404_in_panel_and_api(self):
        get_user_model().objects.create_user(username="staff@example.com", password="Haslo!2345")
        self.client.login(username="staff@example.com", password="Haslo!2345")
        self.assertEqual(self.client.get(reverse("web:schedule")).status_code, 404)
        client = APIClient()
        client.force_authenticate(get_user_model().objects.get(username="staff@example.com"))
        self.assertEqual(client.get("/api/v1/bays/").status_code, 404)

    def test_scoped_returns_only_current_workshop_rows(self):
        class Req:
            user = get_user_model().objects.get(username="b@example.com")
        self.assertFalse(tenancy.scoped(type(self.booking), Req).exists())
        with self.assertRaises(type(self.booking).DoesNotExist):
            tenancy.get_owned(type(self.booking), Req, pk=self.booking.pk)


class TenancyListsAndPublicRoutesTests(TestCase):
    """Lists, searches and public pages never mix two workshops."""

    @classmethod
    def setUpTestData(cls):
        cls.ws_a, cls.service_a = make_workshop("a@example.com")
        cls.ws_b, cls.service_b = make_workshop("b@example.com")
        slot = first_free_slot(cls.ws_a, cls.service_a)
        cls.booking = engine.book(cls.ws_a, cls.service_a, slot.start, customer_name="Anna", phone="501222333",
                                  plate="WX7788K")
        storage.register_deposit(cls.ws_a, customer_name="Anna", phone="501222333", plate="WX7788K",
                                 season="summer", description="205/55 R16")

    def api_as_b(self):
        client = APIClient()
        client.force_authenticate(get_user_model().objects.get(username="b@example.com"))
        return client

    def test_api_lists_of_other_workshop_are_empty(self):
        client = self.api_as_b()
        day = self.booking.start.date().isoformat()
        for url in ("/api/v1/customers/", "/api/v1/tire-deposits/", f"/api/v1/bookings/?date={day}",
                    "/api/v1/customers/?q=Anna", "/api/v1/tire-deposits/?q=WX7788K"):
            with self.subTest(url=url):
                r = client.get(url)
                self.assertEqual(r.status_code, 200)
                rows = r.data["results"] if isinstance(r.data, dict) and "results" in r.data else r.data
                self.assertEqual(list(rows), [])

    def test_web_lists_and_search_of_other_workshop_show_nothing(self):
        self.client.login(username="b@example.com", password="Haslo!2345")
        for url in (reverse("web:customers") + "?q=Anna", reverse("web:storage") + "?q=wx7788",  # query is echoed in the search box, so search lowercase
                    reverse("web:schedule") + f"?d={self.booking.start.date()}"):
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertNotContains(r, "WX7788K")
                self.assertNotContains(r, "501222333")

    def test_domain_searches_are_scoped(self):
        from apps.booking import customers
        self.assertEqual(list(customers.search(self.ws_b, "Anna")), [])
        self.assertEqual(list(storage.search(self.ws_b, "WX7788K")), [])

    def test_public_pages_reject_service_of_another_workshop(self):
        slot = first_free_slot(self.ws_b, self.service_b)
        self.assertEqual(self.client.get(reverse("web:public_slots", args=[self.ws_a.slug, self.service_b.pk]))
                         .status_code, 404)
        r = self.client.post(reverse("web:public_book", args=[self.ws_a.slug, self.service_b.pk]),
                             {"start": slot.start.isoformat(), "name": "X", "phone": "600999888", "plate": "X9",
                              "consent": "on"})
        self.assertEqual(r.status_code, 404)
        r = APIClient().post(f"/api/v1/public/workshops/{self.ws_a.slug}/bookings/",
                             {"service": self.service_b.pk, "start": slot.start.isoformat(), "name": "X",
                              "phone": "600999888", "plate": "X9", "consent": True}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(type(self.booking).objects.filter(plate="X9").count(), 0)

    def test_owner_cannot_create_manual_booking_with_foreign_service(self):
        slot = first_free_slot(self.ws_a, self.service_a)
        r = self.api_as_b().post("/api/v1/bookings/", {"service": self.service_a.pk, "start": slot.start.isoformat(),
                                                       "name": "X", "phone": "600999888", "plate": "X9"},
                                 format="json")
        self.assertIn(r.status_code, (400, 404))
        self.assertEqual(type(self.booking).objects.filter(plate="X9").count(), 0)
