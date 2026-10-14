from test_app.models import Ride, RideRequest


def pending_requests(request):
    """
    pending_request_count: requests waiting for the user's answer, shown on
    the notification bell. It is only counted when a template uses it.
    """
    if not request.user.is_authenticated:
        return {}
    return {
        "pending_request_count": lambda: RideRequest.objects.filter(
            ride__in=Ride.objects.upcoming(),
            ride__driver=request.user,
            status=RideRequest.Status.PENDING,
        ).count(),
    }
