"""SMS seam: SMSAPI backend (fake transport, no network) and the send_sms journal."""
import json
import urllib.error
import urllib.parse

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.notifications import sms
from apps.notifications.backends import SmsapiBackend, SmsError
from apps.notifications.models import SmsMessage

from .factories import make_workshop


class FakeTransport:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, url, data, headers):
        self.calls.append((url, urllib.parse.parse_qs(data.decode()), headers))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return json.dumps(r)


OK = {"count": 1, "list": [{"id": "1460969715572091219", "points": 0.16, "status": "QUEUE"}]}


class SmsapiBackendTests(TestCase):
    def backend(self, *responses, **kw):
        t = FakeTransport(*responses)
        return SmsapiBackend(transport=t, token="tok", sender="Zapik", url="https://main/sms.do",
                             backup_url="https://backup/sms.do", **kw), t

    def test_sends_bearer_request_with_polish_msisdn(self):
        b, t = self.backend(OK)
        self.assertEqual(b.send("600 123 456", "Zażółć"), "1460969715572091219")
        url, params, headers = t.calls[0]
        self.assertEqual(url, "https://main/sms.do")
        self.assertEqual(headers["Authorization"], "Bearer tok")
        self.assertEqual(params["to"], ["48600123456"])
        self.assertEqual(params["message"], ["Zażółć"])
        self.assertEqual(params["from"], ["Zapik"])
        self.assertEqual(params["format"], ["json"])

    def test_falls_back_to_backup_url_when_main_is_unreachable(self):
        b, t = self.backend(urllib.error.URLError("down"), OK)
        b.send("600123456", "x")
        self.assertEqual([c[0] for c in t.calls], ["https://main/sms.do", "https://backup/sms.do"])

    def test_api_error_raises(self):
        b, _ = self.backend({"error": 101, "message": "Authorization failed"})
        with self.assertRaisesMessage(SmsError, "101"):
            b.send("600123456", "x")

    def test_missing_token_raises(self):
        with self.assertRaises(SmsError):
            SmsapiBackend(transport=FakeTransport(), token="")


class FailingBackend:
    def send(self, phone, text):
        raise SmsError("provider down")


@override_settings(SMS_BACKEND="apps.notifications.backends.LocMemSmsBackend")
class SendSmsJournalTests(TestCase):
    def setUp(self):
        sms.outbox.clear()

    def test_success_is_journaled(self):
        ws, _ = make_workshop()
        msg = sms.send_sms("600123456", "hej", workshop=ws, kind="visit_reminder")
        self.assertEqual((msg.status, msg.kind, msg.workshop), ("sent", "visit_reminder", ws))

    @override_settings(SMS_BACKEND="tests.test_sms.FailingBackend")
    def test_failure_is_journaled_not_raised(self):
        msg = sms.send_sms("600123456", "hej")
        self.assertEqual(msg.status, SmsMessage.Status.FAILED)
        self.assertIn("provider down", msg.error)

    def test_owner_sees_only_own_sms_log(self):
        ws, _ = make_workshop()
        other, _ = make_workshop("other@example.com")
        sms.send_sms("600111111", "mine", workshop=ws)
        sms.send_sms("600222222", "theirs", workshop=other)
        self.client.login(username="owner@example.com", password="Haslo!2345")
        r = self.client.get(reverse("web:sms_log"))
        self.assertContains(r, "600111111")
        self.assertNotContains(r, "600222222")


@override_settings(SMS_BACKEND="tests.test_sms.FailingBackend")
class FailedSmsDoesNotBreakBookingTests(TestCase):
    def test_booking_survives_provider_failure(self):
        from apps.booking import reservations
        from .test_web import first_free_slot
        ws, service = make_workshop()
        slot = first_free_slot(ws, service)
        with self.captureOnCommitCallbacks(execute=True):
            b = reservations.reserve_online(ws, service, slot.start,
                                            reservations.CustomerDetails("Jan", "600123456", "X1"), consent=True)
        self.assertTrue(b.pk)
        self.assertEqual(SmsMessage.objects.get().status, "failed")
