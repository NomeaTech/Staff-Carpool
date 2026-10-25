from django.core.management.base import BaseCommand

from rides.ratings import remind


class Command(BaseCommand):
    help = (
        "Tell drivers and passengers about trips they can now rate (rides/ratings.py). "
        "The app does this on each member's first visit of the day; run this from cron "
        "(e.g. hourly) for reminders soon after each trip."
    )

    def handle(self, *args, **options):
        self.stdout.write(f"Sent {remind()} rating reminders.")
