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
