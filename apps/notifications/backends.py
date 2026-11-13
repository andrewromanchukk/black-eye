"""SMS backends. Each has send(phone, text) -> provider message id, or raises SmsError."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger("zapik.sms")


class SmsError(Exception):
    pass


def to_msisdn(phone: str) -> str:
    """Polish 9-digit numbers -> 48XXXXXXXXX; anything else is passed through as digits."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return "48" + digits if len(digits) == 9 else digits


class LogSmsBackend:
    """Local/dev: write the SMS to the log, send nothing."""

    def send(self, phone: str, text: str) -> str:
        logger.info("SMS to %s: %s", phone, text)
        return "log"


class LocMemSmsBackend:
    """Tests: keep messages in apps.notifications.sms.outbox."""

    def send(self, phone: str, text: str) -> str:
        from . import sms
        sms.outbox.append((phone, text))
        return f"locmem-{len(sms.outbox)}"


def urllib_transport(url: str, data: bytes, headers: dict, timeout: float = 10) -> str:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


class SmsapiBackend:
    """SMSAPI.pl — POST /sms.do with an OAuth Bearer token (https://www.smsapi.pl/docs).

    Settings: SMSAPI_TOKEN (required), SMSAPI_SENDER (registered sender name, optional),
    SMSAPI_URL, SMSAPI_BACKUP_URL (used once when the main URL is unreachable).
    """

    def __init__(self, transport=urllib_transport, token=None, sender=None, url=None, backup_url=None):
        self.transport = transport
        self.token = token if token is not None else settings.SMSAPI_TOKEN
        self.sender = sender if sender is not None else settings.SMSAPI_SENDER
        self.url = url or settings.SMSAPI_URL
        self.backup_url = backup_url or settings.SMSAPI_BACKUP_URL
        if not self.token:
            raise SmsError("SMSAPI_TOKEN is not configured")

    def send(self, phone: str, text: str) -> str:
        params = {"to": to_msisdn(phone), "message": text, "format": "json", "encoding": "utf-8"}
        if self.sender:
            params["from"] = self.sender
        data = urllib.parse.urlencode(params).encode()
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/x-www-form-urlencoded"}
        try:
            body = self.transport(self.url, data, headers)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as first:
            if isinstance(first, urllib.error.HTTPError):  # the API answered: do not resend
                body = first.read().decode("utf-8", "replace") if first.fp else ""
            else:
                logger.warning("SMSAPI main URL failed (%s), trying backup", first)
                try:
                    body = self.transport(self.backup_url, data, headers)
                except (urllib.error.URLError, TimeoutError, ConnectionError) as second:
                    raise SmsError(f"SMSAPI unreachable: {second}") from second
        try:
            payload = json.loads(body or "{}")
        except ValueError:
            raise SmsError(f"SMSAPI: unexpected response {body[:120]!r}")
        if "error" in payload:
            raise SmsError(f"SMSAPI error {payload.get('error')}: {payload.get('message', '')}")
        try:
            return str(payload["list"][0]["id"])
        except (KeyError, IndexError, TypeError):
            raise SmsError(f"SMSAPI: no message id in {body[:120]!r}")
