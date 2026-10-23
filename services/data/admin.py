from django.contrib import admin

from .models import DataPlan, DataPlanPrice


class DataPlanPriceInline(admin.TabularInline):
    model = DataPlanPrice
    extra = 0


@admin.register(DataPlan)
class DataPlanAdmin(admin.ModelAdmin):
    list_display = (
        "network", "category", "name", "validity",
        "base_price", "provider_code", "sort_order", "is_active",
    )
    list_editable = ("base_price", "sort_order", "is_active")
    list_filter = ("network", "category", "is_active")
    search_fields = ("name", "provider_code")
    inlines = [DataPlanPriceInline]