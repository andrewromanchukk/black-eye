from django.db import models

from apps.booking.models import Customer
from apps.workshops.models import Workshop


class TireDeposit(models.Model):
    """A customer's tire set stored at the workshop between seasons (przechowalnia)."""

    class Season(models.TextChoices):
        SUMMER = "summer", "Letnie"
        WINTER = "winter", "Zimowe"
        ALL_SEASON = "all", "Całoroczne"

    class Status(models.TextChoices):
        STORED = "stored", "W przechowalni"
        RETURNED = "returned", "Wydane"

    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="tire_deposits")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="tire_deposits")
    plate = models.CharField("Nr rejestracyjny", max_length=16)
    season = models.CharField("Opony", max_length=8, choices=Season.choices)
    description = models.CharField("Opis", max_length=200, help_text="Np. 205/55 R16, Michelin, z felgami")
    location = models.CharField("Miejsce w magazynie", max_length=40, blank=True, help_text="Np. Regał B, półka 3")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.STORED)
    stored_at = models.DateField("Data przyjęcia")
    returned_at = models.DateField("Data wydania", null=True, blank=True)
    reminded_at = models.DateTimeField("Przypomnienie wysłane", null=True, blank=True)

    class Meta:
        ordering = ["-stored_at", "-id"]

    def __str__(self):
        return f"{self.plate} · {self.get_season_display()} · {self.description}"
