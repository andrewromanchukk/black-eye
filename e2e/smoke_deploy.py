"""Smoke test after a deploy: is this Zapik alive and usable? Read-only — safe against production.

Checks (each in a real browser, Chrome via Playwright):
  1. GET /healthz answers 200;
  2. the public booking page of a workshop opens, lists services, and a service shows its booking calendar;
  3. the owner can log in and lands on the schedule.

Nothing is booked or changed. Not part of the regular E2E run (file name does not start with "test").

    SMOKE_BASE_URL=https://zapik.example \\
    SMOKE_WORKSHOP_SLUG=<slug> SMOKE_EMAIL=<owner login> SMOKE_PASSWORD=<password> \\
    python -m tests.junit e2e test-results/smoke.xml 'smoke*.py'

Defaults match the demo data (`manage.py seed_demo`), which CI uses against the image it just built.
After a deploy to ECS: point SMOKE_BASE_URL at the service and pass a dedicated smoke-test owner from secrets.
"""
import os
import re
import unittest

from playwright.sync_api import expect, sync_playwright

from artifacts import record_on_failure

BASE_URL = os.environ.get("SMOKE_BASE_URL", os.environ.get("E2E_BASE_URL", "http://localhost:8000")).rstrip("/")
SLUG = os.environ.get("SMOKE_WORKSHOP_SLUG", "opony-kowalski")
EMAIL = os.environ.get("SMOKE_EMAIL", "demo@zapik.pl")
PASSWORD = os.environ.get("SMOKE_PASSWORD", "ZapikDemo2026")


class SmokeAfterDeploy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        chrome = os.environ.get("E2E_CHROME")
        cls.browser = cls.pw.chromium.launch(executable_path=chrome) if chrome else cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        context = self.browser.new_context(base_url=BASE_URL, locale="pl-PL")
        self.addCleanup(context.close)
        record_on_failure(self, context)
        self.page = context.new_page()
        self.page.set_default_timeout(15_000)

    def test_1_healthz(self):
        response = self.page.request.get("/healthz")
        self.assertEqual(response.status, 200, f"/healthz answered {response.status}: {response.text()[:200]}")

    def test_2_public_booking_page(self):
        response = self.page.goto(f"/w/{SLUG}/")
        self.assertEqual(response.status, 200)
        expect(self.page.get_by_role("heading", name="Wybierz usługę")).to_be_visible()
        service = self.page.locator("a.option").first
        expect(service).to_be_visible()  # the workshop offers at least one service
        service.click()
        expect(self.page.get_by_role("heading", name="Wybierz dzień")).to_be_visible()

    def test_3_owner_login(self):
        self.page.goto("/logowanie/")
        self.page.get_by_label("E-mail").fill(EMAIL)
        self.page.get_by_label("Hasło").fill(PASSWORD)
        self.page.get_by_role("button", name="Zaloguj").click()
        expect(self.page).to_have_url(re.compile(r"^[^?]*/panel/"))  # path, not a ?next=/panel/ on the login page
        expect(self.page.get_by_role("link", name="+ Dodaj wizytę")).to_be_visible()  # the schedule rendered


if __name__ == "__main__":
    unittest.main()
