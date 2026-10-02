from django.contrib import admin
from .models import *

# admin.site.register(Profile)
admin.site.register(Address)
class ViaInline(admin.TabularInline):
    model = Via
    extra = 0


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    inlines = [ViaInline]