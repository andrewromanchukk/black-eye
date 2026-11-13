from django.db import models


class SmsMessage(models.Model):
    """Journal of every SMS Zapik tried to send (audit for the workshop, cost tracking)."""

    class Kind(models.TextChoices):
        BOOKING_CONFIRMATION = "booking_confirmation", "Potwierdzenie rezerwacji"
        VISIT_REMINDER = "visit_reminder", "Przypomnienie o wizycie"
        SEASON_REMINDER = "season_reminder", "Przypomnienie sezonowe"
        OTHER = "other", "Inne"

    class Status(models.TextChoices):
        SENT = "sent", "Wysłany"
        FAILED = "failed", "Błąd"

    workshop = models.ForeignKey("workshops.Workshop", on_delete=models.CASCADE, related_name="sms_messages",
                                 null=True, blank=True)
    phone = models.CharField(max_length=20)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.OTHER)
    text = models.TextField()
    status = models.CharField(max_length=8, choices=Status.choices)
    provider_id = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.phone} · {self.get_kind_display()} · {self.status}"
