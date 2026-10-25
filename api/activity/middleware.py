from datetime import datetime, time

from django.utils import timezone

from .events import anonymise_old_events, record
from .models import Event, Kind

# Mobile browsers say so in their User-Agent ("Mobile" / "Mobi")
MOBILE = "Mobi"


class DailyActivityMiddleware:
    """
    Records an ACTIVE event the first time each day that a logged-in user
    uses the app (not the admin), for counting daily, weekly and monthly
    active users. Only whether it was on a phone or a computer is kept.

    Each of these also anonymises the events that have become old enough
    (events.anonymise_old_events), so no scheduled job is needed. It is a
    single indexed UPDATE, which finds nothing to change on most days.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not request.path.startswith("/admin"):
            today = timezone.localdate()
            # The session remembers it, so that it is only looked up once a day
            if request.session.get("active_on") != today.isoformat():
                start = timezone.make_aware(datetime.combine(today, time.min))
                if not Event.objects.filter(user=user, kind=Kind.ACTIVE, created_at__gte=start).exists():
                    device = "mobile" if MOBILE in request.headers.get("User-Agent", "") else "desktop"
                    record(Kind.ACTIVE, user, device=device)
                    anonymise_old_events()
                request.session["active_on"] = today.isoformat()
        return self.get_response(request)
