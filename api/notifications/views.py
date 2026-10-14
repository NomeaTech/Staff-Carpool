from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Notification

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
    return redirect(notification.url() or "notifications")


@login_required
@require_POST
def mark_all_read(request):
    unread(request.user).update(read_at=timezone.now())
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"unread": 0})
    return redirect(request.POST.get("next") or "notifications")
