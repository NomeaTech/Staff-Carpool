import json
import uuid

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from activity import events
from activity.models import Kind
from . import push
from .models import Notification, PushSubscription

# How many the bell's menu shows
MENU_SIZE = 8
PAGE_SIZE = 30


def unread(user):
    return user.notifications.filter(read_at__isnull=True)


@login_required
@never_cache
def menu(request):
    """The bell's menu, fetched when it is opened (static/js/notifications.js)."""
    return render(request, "notifications/_menu.html", {
        "notifications": request.user.notifications.select_related("ride")[:MENU_SIZE],
        "unread_count": unread(request.user).count(),
    })


@login_required
def notification_list(request):
    page = Paginator(request.user.notifications.select_related("ride"), PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page, "unread_count": unread(request.user).count()})


@login_required
@never_cache
def poll(request):
    """
    The notifications received since ?since= (an ISO time from an earlier
    answer, or the page), for showing them as pop-ups as they arrive, and
    the number unread for the bell. PWA push can later deliver the same
    payloads (Notification.as_payload) without the page asking.
    """
    now = timezone.now()
    since = parse_datetime(request.GET.get("since", "") or "")
    new = []
    if since is not None:
        if timezone.is_naive(since):
            since = timezone.make_aware(since)
        new = [n.as_payload() for n in request.user.notifications.filter(created_at__gt=since).select_related("ride")[:MENU_SIZE]]
    return JsonResponse({"now": now.isoformat(), "unread": unread(request.user).count(), "notifications": new})


@login_required
def open_notification(request, notification_id):
    """Marks the notification read and goes where it leads (the list if nowhere)."""
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if not notification.is_read:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    minutes = round((timezone.now() - notification.created_at).total_seconds() / 60)
    events.record(Kind.NOTIFICATION_OPENED, request.user, kind=notification.kind, minutes=minutes)
    return redirect(notification.url() or "notifications")


@login_required
@require_POST
def mark_all_read(request):
    """Marks all notifications read, or only those about the ride in ?ride= / POST ride."""
    notifications = unread(request.user)
    ride = request.POST.get("ride")
    if ride:
        try:
            notifications = notifications.filter(ride=uuid.UUID(ride))
        except ValueError:
            return JsonResponse({"error": "Not a ride"}, status=400)
    if count := notifications.update(read_at=timezone.now()):
        events.record(Kind.NOTIFICATIONS_READ, request.user, count=count)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"unread": 0})
    # Only back to a page of the app, never to another site
    next_url = request.POST.get("next")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = "notifications"
    return redirect(next_url)


@login_required
@require_POST
def push_subscribe(request):
    """
    Saves this device's push subscription (static/js/push.js), as sent by
    the browser's PushSubscription.toJSON(). A device that was turned on
    for another account moves to this one.
    """
    try:
        data = json.loads(request.body)
        endpoint, keys = data["endpoint"], data["keys"]
        p256dh, auth = keys["p256dh"], keys["auth"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Not a push subscription"}, status=400)
    if not (push.allowed_endpoint(endpoint) and isinstance(p256dh, str) and isinstance(auth, str)
            and len(p256dh) <= 200 and len(auth) <= 100):
        return JsonResponse({"error": "Not a push subscription"}, status=400)

    _subscription, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.headers.get("User-Agent", "")[:300],
        },
    )
    # The browser sends it again on each visit; only turning it on is recorded
    if created:
        events.record(Kind.PUSH_ON, request.user)
    return JsonResponse({"subscribed": True})


@login_required
@require_POST
def push_unsubscribe(request):
    """Forgets this device's push subscription (static/js/push.js)."""
    try:
        endpoint = json.loads(request.body)["endpoint"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "No endpoint"}, status=400)
    if request.user.push_subscriptions.filter(endpoint=endpoint).delete()[0]:
        events.record(Kind.PUSH_OFF, request.user)
    return JsonResponse({"subscribed": False})
