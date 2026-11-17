"""Send SMS reminders ~24 h before visits. Run every hour (cron / ECS Scheduled Task)."""
from django.core.management.base import BaseCommand

from apps.booking.reminders import send_visit_reminders


class Command(BaseCommand):
    help = "Send visit reminders for bookings starting in 20-28 hours"

    def handle(self, *args, **options):
        self.stdout.write(f"Visit reminders sent: {send_visit_reminders()}")
