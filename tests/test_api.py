"""REST API v1 seam (future mobile app)."""
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.booking import engine
from apps.booking.models import Booking

from .factories import make_workshop
from .test_web import first_free_slot


@override_settings(SMS_BACKEND="apps.notifications.backends.LocMemSmsBackend")
class ApiTests(APITestCase):
    def setUp(self):
        self.ws, self.service = make_workshop()

    def auth(self, email="owner@example.com"):
        r = self.client.post("/api/v1/auth/token/", {"username": email, "password": "Haslo!2345"})
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + r.data["token"])

    def test_owner_endpoints_require_token(self):
        self.assertEqual(self.client.get("/api/v1/bookings/").status_code, 401)

    def test_public_slots_and_booking(self):
        r = self.client.get(f"/api/v1/public/workshops/{self.ws.slug}/")
        self.assertEqual(r.data["services"][0]["name"], "Wymiana opon")
        slot = first_free_slot(self.ws, self.service)
        r = self.client.get(f"/api/v1/public/workshops/{self.ws.slug}/services/{self.service.pk}/slots/",
                            {"date": slot.start.date().isoformat()})
        self.assertTrue(r.data)
        payload = {"service": self.service.pk, "start": slot.start.isoformat(), "name": "Jan",
                   "phone": "600123456", "plate": "WWL1", "consent": True}
        r = self.client.post(f"/api/v1/public/workshops/{self.ws.slug}/bookings/", payload, format="json")
        self.assertEqual(r.status_code, 201)
        r = self.client.post(f"/api/v1/public/workshops/{self.ws.slug}/bookings/", payload, format="json")
        self.assertEqual(r.status_code, 409)

    def test_day_bookings_status_and_isolation(self):
        slot = first_free_slot(self.ws, self.service)
        b = engine.book(self.ws, self.service, slot.start, customer_name="J", phone="600123456", plate="X1")
        self.auth()
        r = self.client.get("/api/v1/bookings/", {"date": slot.start.date().isoformat()})
        self.assertEqual(r.data["results"][0]["plate"], "X1")
        r = self.client.post(f"/api/v1/bookings/{b.pk}/status/", {"status": "no_show"}, format="json")
        self.assertEqual(r.data["status"], "no_show")

        make_workshop("other@example.com")
        self.auth("other@example.com")
        self.assertEqual(self.client.get(f"/api/v1/bookings/{b.pk}/").status_code, 404)
        self.assertEqual(Booking.objects.get(pk=b.pk).status, "no_show")

    def test_manual_booking_and_tire_deposits(self):
        self.auth()
        r = self.client.post("/api/v1/bookings/", {"service": self.service.pk, "start": "2030-01-07T09:00:00+01:00",
                                                   "name": "Ola", "phone": "600555666", "plate": "KR7"}, format="json")
        self.assertEqual(r.status_code, 201)
        r = self.client.post("/api/v1/tire-deposits/", {"customer_name": "Ola", "phone": "600555666", "plate": "KR7",
                                                        "season": "winter", "description": "195/65 R15"}, format="json")
        self.assertEqual(r.status_code, 201)
        dep = r.data["id"]
        self.assertEqual(self.client.get("/api/v1/tire-deposits/", {"q": "kr7"}).data["count"], 1)
        self.assertEqual(self.client.post("/api/v1/tire-deposits/remind/", {"ids": [dep]}, format="json").data["sent"], 1)
        self.assertEqual(self.client.post(f"/api/v1/tire-deposits/{dep}/return/").data["status"], "returned")

    def test_service_cannot_use_foreign_bay(self):
        other_ws, _ = make_workshop("other@example.com")
        self.auth()
        r = self.client.post("/api/v1/services/", {"name": "X", "duration_min": 30,
                                                   "bays": [other_ws.bays.first().pk]}, format="json")
        self.assertEqual(r.status_code, 400)


class PublicConsentTests(APITestCase):
    def test_public_booking_without_consent_is_400(self):
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        r = self.client.post(f"/api/v1/public/workshops/{ws.slug}/bookings/", {
            "service": service.pk, "start": slot.start.isoformat(), "name": "Jan", "phone": "600123456",
            "plate": "X1"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("consent", r.data)


class CustomerApiTests(APITestCase):
    def test_search_card_and_reminder_toggle(self):
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        b = engine.book(ws, service, slot.start, customer_name="Anna", phone="501222333", plate="WX7788K")
        r = self.client.post("/api/v1/auth/token/", {"username": "owner@example.com", "password": "Haslo!2345"})
        self.client.credentials(HTTP_AUTHORIZATION="Token " + r.data["token"])

        r = self.client.get("/api/v1/customers/", {"q": "wx 7788"})
        self.assertEqual([c["name"] for c in r.data["results"]], ["Anna"])
        r = self.client.get(f"/api/v1/customers/{b.customer_id}/")
        self.assertEqual(r.data["plates"], ["WX7788K"])
        self.assertEqual(r.data["bookings"][0]["id"], b.pk)
        self.assertEqual(r.data["tire_deposits"], [])

        self.assertTrue(self.client.get("/api/v1/workshop/").data["visit_reminders"])
        r = self.client.patch("/api/v1/workshop/", {"visit_reminders": False}, format="json")
        self.assertFalse(r.data["visit_reminders"])
        ws.refresh_from_db()
        self.assertFalse(ws.visit_reminders)
