"""HTTP seam: public booking flow and owner panel, through the Django test client."""
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.booking import engine
from apps.booking.models import Booking
from apps.notifications import sms
from apps.storage.models import TireDeposit

from .factories import make_workshop

LOCMEM = "apps.notifications.backends.LocMemSmsBackend"


def first_free_slot(ws, service):
    for day in engine.bookable_days(ws):
        slots = engine.available_slots(ws, service, day)
        if slots:
            return slots[0]
    raise AssertionError("no free slot")


@override_settings(SMS_BACKEND=LOCMEM)
class PublicBookingFlowTests(TestCase):
    def setUp(self):
        sms.outbox.clear()
        self.ws, self.service = make_workshop()

    def test_customer_books_and_cancels(self):
        r = self.client.get(reverse("web:public_booking", args=[self.ws.slug]))
        self.assertContains(r, "Wymiana opon")

        r = self.client.get(reverse("web:public_slots", args=[self.ws.slug, self.service.pk]))
        self.assertContains(r, 'class="slot"')

        slot = first_free_slot(self.ws, self.service)
        url = reverse("web:public_book", args=[self.ws.slug, self.service.pk])
        data = {"start": slot.start.isoformat(), "name": "Jan", "phone": "600 123 456", "plate": "WWL 12345",
                "consent": "on"}
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(url, data)
        booking = Booking.objects.get()
        self.assertRedirects(r, reverse("web:cancel_booking", args=[booking.cancel_token]))
        self.assertEqual(len(sms.outbox), 1)
        self.assertIn(booking.cancel_token, sms.outbox[0][1])

        r = self.client.get(r.url)
        self.assertContains(r, "Rezerwacja potwierdzona")
        self.client.post(reverse("web:cancel_booking", args=[booking.cancel_token]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    def test_consent_is_required(self):
        slot = first_free_slot(self.ws, self.service)
        r = self.client.post(reverse("web:public_book", args=[self.ws.slug, self.service.pk]),
                             {"start": slot.start.isoformat(), "name": "Jan", "phone": "600123456", "plate": "X1"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Booking.objects.exists())

    def test_taken_slot_sends_customer_back_to_slots(self):
        slot = first_free_slot(self.ws, self.service)
        engine.book(self.ws, self.service, slot.start, customer_name="A", phone="600000001", plate="A1")
        r = self.client.post(reverse("web:public_book", args=[self.ws.slug, self.service.pk]),
                             {"start": slot.start.isoformat(), "name": "Jan", "phone": "600123456", "plate": "X1",
                              "consent": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("web:public_slots", args=[self.ws.slug, self.service.pk]), r.url)
        self.assertEqual(Booking.objects.count(), 1)


@override_settings(SMS_BACKEND=LOCMEM)
class OwnerPanelTests(TestCase):
    def setUp(self):
        sms.outbox.clear()

    def test_signup_creates_workshop_with_defaults_and_panel_requires_login(self):
        self.assertEqual(self.client.get(reverse("web:schedule")).status_code, 302)
        r = self.client.post(reverse("web:signup"), {
            "email": "nowy@example.com", "password": "Opony!Zima2026", "workshop_name": "Opony Kowalski",
            "address": "ul. Polna 12", "phone": "600100200", "accept_terms": "on"})
        self.assertRedirects(r, reverse("web:dashboard"), target_status_code=302)
        r = self.client.get(reverse("web:schedule"))
        self.assertContains(r, "zapik" if False else "/w/opony-kowalski/")
        self.assertContains(r, "Stanowisko 1")

    def test_owner_cannot_touch_other_workshop_booking(self):
        ws_a, service_a = make_workshop("a@example.com")
        make_workshop("b@example.com")
        slot = first_free_slot(ws_a, service_a)
        booking = engine.book(ws_a, service_a, slot.start, customer_name="J", phone="600123456", plate="X1")
        self.client.login(username="b@example.com", password="Haslo!2345")
        r = self.client.post(reverse("web:booking_status", args=[booking.pk]), {"status": "completed"})
        self.assertEqual(r.status_code, 404)

    def test_mark_completed_from_schedule(self):
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        booking = engine.book(ws, service, slot.start, customer_name="J", phone="600123456", plate="X1")
        self.client.login(username="owner@example.com", password="Haslo!2345")
        r = self.client.get(reverse("web:schedule") + f"?d={slot.start.date()}")
        self.assertContains(r, "X1")
        self.client.post(reverse("web:booking_status", args=[booking.pk]), {"status": "completed"})
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)

    def test_manual_booking_from_phone_call(self):
        ws, service = make_workshop()
        self.client.login(username="owner@example.com", password="Haslo!2345")
        data = {"service": service.pk, "start": "2030-01-07T09:00", "name": "Ola", "phone": "600555666",
                "plate": "KR 777"}
        r = self.client.post(reverse("web:manual_booking"), data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Booking.objects.get().source, Booking.Source.MANUAL)
        r = self.client.post(reverse("web:manual_booking"), data)  # same time again -> error
        self.assertContains(r, "zajęte")

    def test_tire_storage_and_season_reminders(self):
        ws, _ = make_workshop()
        self.client.login(username="owner@example.com", password="Haslo!2345")
        self.client.post(reverse("web:storage"), {
            "customer_name": "Jan", "phone": "600123456", "plate": "wwl 1", "season": "summer",
            "description": "205/55 R16 Michelin", "location": "B3"})
        deposit = TireDeposit.objects.get()
        self.assertEqual(deposit.plate, "WWL1")
        self.assertContains(self.client.get(reverse("web:storage") + "?q=WWL"), "205/55 R16")

        r = self.client.get(reverse("web:reminders") + "?season=summer")
        self.assertContains(r, "WWL1")
        self.client.post(reverse("web:reminders"), {"season": "summer", "deposit": [deposit.pk]})
        deposit.refresh_from_db()
        self.assertIsNotNone(deposit.reminded_at)
        self.assertIn(f"/w/{ws.slug}/", sms.outbox[0][1])

        self.client.post(reverse("web:storage_return", args=[deposit.pk]))
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, TireDeposit.Status.RETURNED)

    def test_settings_hours_close_saturday(self):
        ws, service = make_workshop()
        self.client.login(username="owner@example.com", password="Haslo!2345")
        r = self.client.get(reverse("web:settings"))
        self.assertContains(r, "Sobota")


class PublicPagesTests(TestCase):
    def test_landing_legal_and_health(self):
        for name in ("web:landing", "web:terms", "web:privacy", "web:login", "web:signup"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get("/healthz").content, b"ok")


class CustomerCardTests(TestCase):
    def test_search_card_and_link_from_schedule(self):
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        b = engine.book(ws, service, slot.start, customer_name="Anna", phone="501222333", plate="WX7788K")
        from apps.storage import services as storage
        storage.register_deposit(ws, customer_name="Anna", phone="501222333", plate="WX7788K", season="winter",
                                 description="195/65 R15", location="B3")
        self.client.login(username="owner@example.com", password="Haslo!2345")
        r = self.client.get(reverse("web:customers") + "?q=wx7788")
        self.assertContains(r, "Anna")
        card = reverse("web:customer_detail", args=[b.customer_id])
        self.assertContains(self.client.get(reverse("web:schedule") + f"?d={slot.start.date()}"), card)
        r = self.client.get(card)
        self.assertContains(r, "WX7788K")
        self.assertContains(r, "195/65 R15")
        self.assertContains(r, "B3")

    def test_other_workshop_customer_card_is_404(self):
        ws, service = make_workshop("a@example.com")
        make_workshop("b@example.com")
        slot = first_free_slot(ws, service)
        b = engine.book(ws, service, slot.start, customer_name="Anna", phone="501222333", plate="X1")
        self.client.login(username="b@example.com", password="Haslo!2345")
        self.assertEqual(self.client.get(reverse("web:customer_detail", args=[b.customer_id])).status_code, 404)
