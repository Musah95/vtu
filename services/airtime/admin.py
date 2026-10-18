from django.contrib import admin

from .models import AirtimePricing, Network


class AirtimePricingInline(admin.TabularInline):
    model = AirtimePricing
    extra = 0


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "min_amount", "max_amount", "is_active")
    list_editable = ("is_active",)
    inlines = [AirtimePricingInline]