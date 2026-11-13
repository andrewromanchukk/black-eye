"""SMS sending behind one interface.

    send_sms(phone, text, *, workshop=None, kind="other") -> SmsMessage

The backend is chosen by settings.SMS_BACKEND (log / locmem / SMSAPI.pl). Every call
is journaled in SmsMessage. Provider failures are recorded (status=failed) and logged,
never raised: a failed SMS must not break a booking.
"""
import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger("zapik.sms")
outbox: list[tuple[str, str]] = []  # filled by LocMemSmsBackend in tests


def get_backend():
    return import_string(settings.SMS_BACKEND)()


def send_sms(phone: str, text: str, *, workshop=None, kind: str = "other"):
    from .backends import SmsError
    from .models import SmsMessage

    msg = SmsMessage(workshop=workshop, phone=phone, kind=kind, text=text)
    try:
        msg.provider_id = get_backend().send(phone, text) or ""
        msg.status = SmsMessage.Status.SENT
    except SmsError as e:
        msg.status, msg.error = SmsMessage.Status.FAILED, str(e)[:300]
        logger.error("SMS to %s failed: %s", phone, e)
    msg.save()
    return msg
