from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.booking import engine
from apps.booking.reminders import send_visit_reminders
from apps.notifications import sms
from apps.notifications.models import SmsMessage

from .factories import NOW, at, make_workshop

TUESDAY = NOW.date() + timedelta(days=1)


@override_settings(SMS_BACKEND="apps.notifications.backends.LocMemSmsBackend")
class VisitReminderTests(TestCase):
    def setUp(self):
        sms.outbox.clear()
        self.ws, self.service = make_workshop(bays=2)

    def book(self, start, phone="600123456"):
        return engine.book(self.ws, self.service, start, customer_name="Jan", phone=phone, plate="X1", now=NOW)

    def test_reminds_only_bookings_20_to_28_hours_ahead(self):
        # NOW = Monday 07:00 -> window Tuesday 03:00..11:00
        due = self.book(at(10, day=TUESDAY))
        too_late = self.book(at(12, day=TUESDAY), phone="600000002")
        too_soon = self.book(at(14), phone="600000003")
        self.assertEqual(send_visit_reminders(now=NOW), 1)
        self.assertEqual(sms.outbox[0][0], "600123456")
        self.assertIn(due.cancel_token, sms.outbox[0][1])
        too_late.refresh_from_db()
        too_soon.refresh_from_db()
        self.assertIsNone(too_late.reminder_sent_at)
        self.assertIsNone(too_soon.reminder_sent_at)

    def test_second_run_does_not_duplicate(self):
        self.book(at(10, day=TUESDAY))
        send_visit_reminders(now=NOW)
        self.assertEqual(send_visit_reminders(now=NOW + timedelta(hours=1)), 0)
        self.assertEqual(len(sms.outbox), 1)

    def test_cancelled_booking_and_disabled_workshop_get_nothing(self):
        engine.cancel(self.book(at(10, day=TUESDAY)))
        self.book(at(9, day=TUESDAY), phone="600000009")
        self.ws.visit_reminders = False
        self.ws.save()
        self.assertEqual(send_visit_reminders(now=NOW), 0)

    @override_settings(SMS_BACKEND="tests.test_sms.FailingBackend")
    def test_failed_sms_is_retried_next_run(self):
        b = self.book(at(10, day=TUESDAY))
        self.assertEqual(send_visit_reminders(now=NOW), 0)
        b.refresh_from_db()
        self.assertIsNone(b.reminder_sent_at)
        self.assertEqual(SmsMessage.objects.get().kind, "visit_reminder")

    def test_management_command_runs(self):
        call_command("send_visit_reminders", stdout=open("/dev/null", "w"))
