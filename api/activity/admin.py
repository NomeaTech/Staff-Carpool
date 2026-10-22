from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """The activity log, read only: events are only ever recorded by the app."""
    list_display = ("created_at", "kind", "user", "ride_id")
    list_filter = ("kind", "created_at")
    search_fields = ("user__email",)
    raw_id_fields = ("user",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
