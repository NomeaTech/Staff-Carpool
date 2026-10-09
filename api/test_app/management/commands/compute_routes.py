from django.core.management.base import BaseCommand

from test_app.models import Ride
from test_app.routes import build_route


class Command(BaseCommand):
    help = (
        "Store the driving route of rides that do not have one yet, e.g. rides "
        "created before routes were added. Run with --all to recompute every route."
    )

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Recompute the routes of all rides")

    def handle(self, *args, **options):
        rides = Ride.objects.prefetch_related("via_points")
        if not options["all"]:
            rides = rides.filter(route__isnull=True)

        updated = 0
        for ride in rides:
            route = build_route(ride)
            if route is None:
                self.stdout.write(f"Skipped ride {ride.pk}: no start or destination")
                continue
            ride.route = route
            ride.save(update_fields=["route"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Stored the route of {updated} ride(s)"))
