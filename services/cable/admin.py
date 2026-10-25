from django.contrib import admin

from .models import CablePackage, CablePackagePrice, SmartcardVerification


class CablePackagePriceInline(admin.TabularInline):
    model = CablePackagePrice
    extra = 0
    fields = ("role", "mode", "value")


@admin.register(CablePackage)
class CablePackageAdmin(admin.ModelAdmin):
    list_display = ("operator", "name", "validity", "base_price", "provider_code", "sort_order", "is_active")
    list_editable = ("base_price", "sort_order", "is_active")
    list_filter = ("operator", "is_active")
    search_fields = ("name", "provider_code")
    inlines = [CablePackagePriceInline]


@admin.register(SmartcardVerification)
class SmartcardVerificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "operator", "smartcard", "customer_name", "expires_at")
    search_fields = ("smartcard", "customer_name", "user__username")
    list_filter = ("operator",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False