"""End-to-end checks in a real browser (Chromium via Playwright) against a running Zapik with demo data.

Covers release checks 1, 2 and 4:
  - customer books on the public page -> slot is gone -> owner logs in, sees it in the schedule, marks it done;
  - owner adds a manual (phone) booking from the panel and sees it in the schedule.
Each scenario runs on a desktop and a 375px phone; on the phone the pages must not scroll horizontally.

    E2E_BASE_URL=http://localhost:8000 python -m unittest discover -s e2e -v

Needs the demo workshop from `manage.py seed_demo` (slug opony-kowalski, demo@zapik.pl / ZapikDemo2026).
E2E_CHROME=/path/to/chrome uses a local Chrome instead of Playwright's Chromium.
"""
import os
import random
import re
import unittest
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

from artifacts import record_on_failure

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
SLUG = "opony-kowalski"
SERVICE = "Wyważanie kół"
OWNER_EMAIL, OWNER_PASSWORD = "demo@zapik.pl", "ZapikDemo2026"

VIEWPORTS = {
    "desktop": {"viewport": {"width": 1280, "height": 800}},
    "phone": {"viewport": {"width": 375, "height": 812}, "is_mobile": True, "has_touch": True},
}


class BookingFlowE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        chrome = os.environ.get("E2E_CHROME")
        cls.browser = cls.pw.chromium.launch(executable_path=chrome) if chrome else cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def new_page(self, device):
        context = self.browser.new_context(base_url=BASE_URL, locale="pl-PL", **VIEWPORTS[device])
        self.addCleanup(context.close)
        record_on_failure(self, context)
        page = context.new_page()
        page.set_default_timeout(10_000)
        return page

    def assert_no_horizontal_scroll(self, page):
        # clientWidth, not innerWidth: a phone browser widens innerWidth to the content and hides the overflow.
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertLessEqual(overflow, 0, f"{page.url}: page is {overflow}px wider than the screen")

    def book_slot(self, page, device, plate):
        """Customer books the first free slot. Returns (slot href, booked date YYYY-MM-DD)."""
        page.goto(f"/w/{SLUG}/")
        if device == "phone":
            self.assert_no_horizontal_scroll(page)
        page.get_by_role("link", name=re.compile(SERVICE)).click()

        slot = page.locator("a.slot").first
        expect(slot).to_be_visible()
        if device == "phone":
            self.assert_no_horizontal_scroll(page)
        href = slot.get_attribute("href")
        start = parse_qs(urlparse(href).query)["start"][0]
        slot.click()

        page.get_by_label("Imię").fill("Test E2E")
        page.get_by_label("Telefon").fill("600 999 888")
        page.get_by_label("Nr rejestracyjny").fill(plate)
        page.get_by_label(re.compile("Akceptuję politykę prywatności")).check()
        if device == "phone":
            self.assert_no_horizontal_scroll(page)
        page.get_by_role("button", name=re.compile("Rezerwuję")).click()

        expect(page.get_by_text("Rezerwacja potwierdzona")).to_be_visible()
        expect(page.get_by_text(plate)).to_be_visible()
        return href, start[:10]

    def run_flow(self, device):
        plate = f"E2E{random.randint(10000, 99999)}"  # stored without spaces

        # 1. Public booking page -> slot booked; the booked slot is no longer offered.
        page = self.new_page(device)
        href, day = self.book_slot(page, device, plate)
        page.goto(f"/w/{SLUG}/{href.split('/')[3]}/?d={day}")
        expect(page.locator(f'a.slot[href="{href}"]')).to_have_count(0)

        # 2. Owner logs in, sees the booking in the schedule and marks it completed.
        page = self.owner_page(device)
        page.goto(f"/panel/grafik/?d={day}")
        if device == "phone":
            self.assert_no_horizontal_scroll(page)
        card = page.locator("article.booking-card", has_text=plate)
        expect(card).to_have_count(1)
        expect(card).to_contain_text(SERVICE)
        expect(card).to_contain_text("Potwierdzona")
        card.get_by_role("button", name="Wykonano").click()
        expect(page.locator("article.booking-card", has_text=plate)).to_contain_text("Wykonana")

    def owner_page(self, device):
        page = self.new_page(device)
        page.goto("/logowanie/")
        page.get_by_label("E-mail").fill(OWNER_EMAIL)
        page.get_by_label("Hasło").fill(OWNER_PASSWORD)
        page.get_by_role("button", name="Zaloguj").click()
        page.wait_for_url("**/panel/**")
        return page

    def run_manual_booking(self, device):
        """Owner takes a phone call and books it by hand: evening time (outside opening hours is allowed).

        Desktop and phone book different days, and if the time is already taken (e.g. a local rerun on the same
        database), the next evening slot is tried — so the two runs never collide by chance."""
        plate = f"TEL{random.randint(10000, 99999)}"
        day = (date.today() + timedelta(days=1 if device == "desktop" else 2)).isoformat()

        page = self.owner_page(device)
        for hour, minute in ((h, m) for h in range(18, 23) for m in (0, 30)):
            start = f"{day}T{hour:02d}:{minute:02d}"
            page.goto(f"/panel/wizyty/nowa/?d={day}")
            if device == "phone":
                self.assert_no_horizontal_scroll(page)
            page.get_by_label("Usługa").select_option(label=SERVICE)
            page.get_by_label("Początek").fill(start)
            page.get_by_label("Imię").fill("Klient z telefonu")
            page.get_by_label("Telefon").fill("600 777 666")
            page.get_by_label("Nr rejestracyjny").fill(plate)
            page.get_by_role("button", name="Dodaj wizytę").click()
            page.wait_for_load_state()
            if "/panel/grafik/" in page.url:
                break
            expect(page.get_by_role("alert")).to_contain_text("zajęte")  # only "time taken" may make us retry
        else:
            self.fail(f"no free evening time on {day}")

        expect(page.get_by_text("Wizyta dodana.")).to_be_visible()
        expect(page).to_have_url(re.compile(rf"/panel/grafik/\?d={day}$"))
        if device == "phone":
            self.assert_no_horizontal_scroll(page)
        card = page.locator("article.booking-card", has_text=plate)
        expect(card).to_have_count(1)
        expect(card).to_contain_text(SERVICE)
        expect(card).to_contain_text("tel.")  # marked as a phone booking
        expect(card).to_contain_text(start[-5:])  # HH:MM

    def test_booking_flow_desktop(self):
        self.run_flow("desktop")

    def test_booking_flow_phone(self):
        self.run_flow("phone")

    def test_manual_booking_desktop(self):
        self.run_manual_booking("desktop")

    def test_manual_booking_phone(self):
        self.run_manual_booking("phone")


if __name__ == "__main__":
    unittest.main()
