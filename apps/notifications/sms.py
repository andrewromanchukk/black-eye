"""SMS sending behind one interface: send_sms(phone, text).

The backend is chosen by settings.SMS_BACKEND. The prototype ships only LogSmsBackend
(writes to the log); a real provider (e.g. SMSAPI.pl) is a new backend class.
"""
from django.conf import settings
from django.utils.module_loading import import_string

outbox: list[tuple[str, str]] = []  # filled by LocMemSmsBackend in tests


def get_backend():
    return import_string(settings.SMS_BACKEND)()


def send_sms(phone: str, text: str) -> None:
    get_backend().send(phone, text)
