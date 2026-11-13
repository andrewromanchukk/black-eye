from datetime import time

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

WEEKDAYS = [
    (0, "Poniedziałek"),
    (1, "Wtorek"),
    (2, "Środa"),
    (3, "Czwartek"),
    (4, "Piątek"),
    (5, "Sobota"),
    (6, "Niedziela"),
]

DEFAULT_HOURS = {0: (time(8), time(17)), 1: (time(8), time(17)), 2: (time(8), time(17)),
                 3: (time(8), time(17)), 4: (time(8), time(17)), 5: (time(8), time(13))}


class Workshop(models.Model):
    """A tire shop / car workshop using Zapik. One Owner per Workshop in the MVP."""

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workshop")
    name = models.CharField("Nazwa", max_length=120)
    slug = models.SlugField("Adres strony", max_length=60, unique=True)
    address = models.CharField("Adres", max_length=200)
    phone = models.CharField("Telefon", max_length=20)
    slot_step_min = models.PositiveSmallIntegerField(
        "Krok terminów (min)", default=30, choices=[(15, "15 min"), (30, "30 min"), (60, "60 min")])
    booking_horizon_days = models.PositiveSmallIntegerField(
        "Zapisy na ile dni do przodu", default=30, validators=[MinValueValidator(1), MaxValueValidator(180)])
    min_notice_min = models.PositiveSmallIntegerField(
        "Minimalne wyprzedzenie (min)", default=60, validators=[MaxValueValidator(7 * 24 * 60)])
    visit_reminders = models.BooleanField(
        "SMS z przypomnieniem dzień przed wizytą", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @staticmethod
    def unique_slug_for(name: str) -> str:
        base = slugify(name)[:50] or "warsztat"
        slug, n = base, 2
        while Workshop.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    def create_default_hours(self):
        for weekday in range(7):
            opens, closes = DEFAULT_HOURS.get(weekday, (None, None))
            OpeningHours.objects.update_or_create(
                workshop=self, weekday=weekday,
                defaults={"opens": opens, "closes": closes, "is_closed": weekday not in DEFAULT_HOURS},
            )


class OpeningHours(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="opening_hours")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    is_closed = models.BooleanField("Zamknięte", default=False)
    opens = models.TimeField("Otwarcie", null=True, blank=True)
    closes = models.TimeField("Zamknięcie", null=True, blank=True)

    class Meta:
        ordering = ["weekday"]
        constraints = [models.UniqueConstraint(fields=["workshop", "weekday"], name="uniq_hours_per_weekday")]

    def __str__(self):
        return f"{self.get_weekday_display()}: {'zamknięte' if self.is_closed else f'{self.opens}-{self.closes}'}"


class Bay(models.Model):
    """A physical place that serves one car at a time (lift, tire station)."""

    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="bays")
    name = models.CharField("Nazwa", max_length=60)
    is_active = models.BooleanField("Aktywne", default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name


class Service(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="services")
    name = models.CharField("Nazwa", max_length=120)
    duration_min = models.PositiveSmallIntegerField(
        "Czas trwania (min)", validators=[MinValueValidator(5), MaxValueValidator(8 * 60)])
    price = models.DecimalField("Cena (zł)", max_digits=8, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField("Widoczna dla klientów", default=True)
    bays = models.ManyToManyField(
        Bay, blank=True, related_name="services", verbose_name="Stanowiska",
        help_text="Puste = usługa dostępna na wszystkich stanowiskach.")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name
