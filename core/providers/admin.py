from django.contrib import admin

from .models import ProviderRoute


@admin.register(ProviderRoute)
class ProviderRouteAdmin(admin.ModelAdmin):
    list_display = ("service", "provider", "priority", "is_active")
    list_editable = ("priority", "is_active")
    list_filter = ("service", "is_active")