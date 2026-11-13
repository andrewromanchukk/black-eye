from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model

from apps.workshops.models import Bay, Service, Workshop

WARSAW = ZoneInfo("Europe/Warsaw")
# Monday 2026-11-16 07:00 local: a fixed "now" for deterministic tests
NOW = datetime(2026, 11, 16, 7, 0, tzinfo=WARSAW)
MONDAY = NOW.date()


def at(hour, minute=0, day=MONDAY):
    return datetime.combine(day, time(hour, minute), tzinfo=WARSAW)


def make_workshop(email="owner@example.com", bays=1, **kw):
    user = get_user_model().objects.create_user(username=email, email=email, password="Haslo!2345")
    ws = Workshop.objects.create(owner=user, name=kw.pop("name", "Opony Test"), slug=kw.pop("slug", email.split("@")[0]),
                                 address="ul. Polna 1", phone="600100200", min_notice_min=kw.pop("min_notice_min", 0), **kw)
    ws.create_default_hours()  # Mon-Fri 8-17, Sat 8-13
    for i in range(bays):
        Bay.objects.create(workshop=ws, name=f"Stanowisko {i + 1}", position=i)
    service = Service.objects.create(workshop=ws, name="Wymiana opon", duration_min=60, price=120)
    return ws, service
