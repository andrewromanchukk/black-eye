"""Browser regression tests for bugs that were fixed once. Same setup as test_booking_flow.py (demo data, E2E_BASE_URL)."""
import os
import unittest

from playwright.sync_api import sync_playwright

from artifacts import record_on_failure

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000").rstrip("/")
OWNER_EMAIL, OWNER_PASSWORD = "demo@zapik.pl", "ZapikDemo2026"

PUBLIC_PAGES = ["/", "/w/opony-kowalski/", "/logowanie/"]
PANEL_PAGES = ["/panel/", "/panel/grafik/", "/panel/wizyty/nowa/", "/panel/ustawienia/", "/panel/stanowiska/",
               "/panel/uslugi/", "/panel/przechowalnia/", "/panel/przypomnienia/", "/panel/sms/", "/panel/klienci/"]


class NoHorizontalScrollOn375pxTests(unittest.TestCase):
    """Bug (13.11): on a 375px phone, panel pages with tables were wider than the screen and scrolled sideways."""

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
        self.context = self.browser.new_context(base_url=BASE_URL, locale="pl-PL", is_mobile=True, has_touch=True,
                                                viewport={"width": 375, "height": 812})
        self.addCleanup(self.context.close)
        record_on_failure(self, self.context)
        self.page = self.context.new_page()
        self.page.set_default_timeout(10_000)

    def assert_fits(self, path):
        with self.subTest(page=path):
            self.page.goto(path)
            # clientWidth, not innerWidth: a phone browser widens innerWidth to the content and hides the overflow.
            overflow = self.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            self.assertLessEqual(overflow, 0, f"{path} is {overflow}px wider than a 375px screen")

    def test_public_pages_fit(self):
        for path in PUBLIC_PAGES:
            self.assert_fits(path)

    def test_panel_pages_fit(self):
        self.page.goto("/logowanie/")
        self.page.get_by_label("E-mail").fill(OWNER_EMAIL)
        self.page.get_by_label("Hasło").fill(OWNER_PASSWORD)
        self.page.get_by_role("button", name="Zaloguj").click()
        self.page.wait_for_url("**/panel/**")
        for path in PANEL_PAGES:
            self.assert_fits(path)
        self.page.goto("/panel/klienci/")
        card = self.page.locator('a[href^="/panel/klienci/"]').first.get_attribute("href")
        self.assert_fits(card)


if __name__ == "__main__":
    unittest.main()
