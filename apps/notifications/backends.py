import logging

logger = logging.getLogger("zapik.sms")


class LogSmsBackend:
    def send(self, phone: str, text: str) -> None:
        logger.info("SMS to %s: %s", phone, text)


class LocMemSmsBackend:
    def send(self, phone: str, text: str) -> None:
        from . import sms
        sms.outbox.append((phone, text))
