"""End-to-end checks in a real browser (Chromium via Playwright) against a running Zapik with demo data.

Covers release checks 1–2: public booking page -> slot booked -> owner sees it in the panel and marks it done.
Each scenario runs on a desktop and a phone viewport; on the phone the page must not scroll horizontally.

    E2E_BASE_URL=http://localhost:8000 python -m unittest discover -s e2e -v

Needs the demo workshop from `manage.py seed_demo` (slug opony-kowalski, demo@zapik.pl / ZapikDemo2026).
E2E_CHROME=/path/to/chrome uses a local Chrome instead of Playwright's Chromium.
"""
import os
import random
import re
import unittest
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
SLUG = "opony-kowalski"
SERVICE = "Wyważanie kół"
OWNER_EMAIL, OWNER_PASSWORD = "demo@zapik.pl", "ZapikDemo2026"

VIEWPORTS = {
    "desktop": {"viewport": {"width": 1280, "height": 800}},
    "phone": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True},
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
        page = context.new_page()
        page.set_default_timeout(10_000)
        return page

    def assert_no_horizontal_scroll(self, page):
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
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
        page = self.new_page(device)
        page.goto("/logowanie/")
        page.get_by_label("E-mail").fill(OWNER_EMAIL)
        page.get_by_label("Hasło").fill(OWNER_PASSWORD)
        page.get_by_role("button", name="Zaloguj").click()
        page.goto(f"/panel/grafik/?d={day}")
        if device == "phone":
            self.assert_no_horizontal_scroll(page)
        card = page.locator("article.booking-card", has_text=plate)
        expect(card).to_have_count(1)
        expect(card).to_contain_text(SERVICE)
        expect(card).to_contain_text("Potwierdzona")
        card.get_by_role("button", name="Wykonano").click()
        expect(page.locator("article.booking-card", has_text=plate)).to_contain_text("Wykonana")

    def test_booking_flow_desktop(self):
        self.run_flow("desktop")

    def test_booking_flow_phone(self):
        self.run_flow("phone")


if __name__ == "__main__":
    unittest.main()
