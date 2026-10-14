def notifications(request):
    """
    unread_notification_count, shown on the bell, in the side menu and on
    the dock. Counted once, and only when a template uses it.
    """
    if not request.user.is_authenticated:
        return {}
    counted = {}

    def unread_notification_count():
        if "count" not in counted:
            counted["count"] = request.user.notifications.filter(read_at__isnull=True).count()
        return counted["count"]

    return {"unread_notification_count": unread_notification_count}
