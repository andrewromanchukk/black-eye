"""Create a demo workshop with bays, services, bookings and stored tires.

    python manage.py seed_demo            -> login demo@zapik.pl / ZapikDemo2026
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.booking import engine
from apps.storage import services as storage
from apps.workshops.models import Bay, Service, Workshop

EMAIL, PASSWORD = "demo@zapik.pl", "ZapikDemo2026"


class Command(BaseCommand):
    help = "Seed a demo workshop"

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username=EMAIL).exists():
            self.stdout.write("Demo already exists.")
            return
        user = User.objects.create_user(username=EMAIL, email=EMAIL, password=PASSWORD)
        ws = Workshop.objects.create(owner=user, name="Opony Kowalski", slug="opony-kowalski",
                                     address="ul. Polna 12, 05-230 Kobyłka", phone="600 100 200", min_notice_min=30)
        ws.create_default_hours()
        tires = Bay.objects.create(workshop=ws, name="Stanowisko opon", position=0)
        lift = Bay.objects.create(workshop=ws, name="Podnośnik 1", position=1)
        swap = Service.objects.create(workshop=ws, name="Wymiana opon — 4 koła", duration_min=45, price=120, position=0)
        swap.bays.add(tires, lift)
        balance = Service.objects.create(workshop=ws, name="Wyważanie kół", duration_min=30, price=60, position=1)
        balance.bays.add(tires)
        oil = Service.objects.create(workshop=ws, name="Wymiana oleju", duration_min=60, price=180, position=2)
        oil.bays.add(lift)

        people = [("Jan", "600123456", "WWL12345"), ("Anna", "501222333", "WX7788K"),
                  ("Piotr", "602444555", "WPR5512"), ("Ola", "698111000", "KR4P123")]
        made = 0
        for day in engine.bookable_days(ws)[:3]:
            for service in (swap, balance, oil):
                slots = engine.available_slots(ws, service, day)
                for slot in slots[made % 3:: max(len(slots) // 2, 1)][:2]:
                    name, phone, plate = people[made % len(people)]
                    engine.book(ws, service, slot.start, customer_name=name, phone=phone, plate=plate)
                    made += 1
        for name, phone, plate in people:
            storage.register_deposit(ws, customer_name=name, phone=phone, plate=plate, season="summer",
                                     description="205/55 R16, z felgami", location=f"Regał A{made % 5 + 1}",
                                     stored_at=date(2026, 10, 20))
        self.stdout.write(self.style.SUCCESS(f"Demo: /w/{ws.slug}/  login {EMAIL} / {PASSWORD}  ({made} bookings)"))
