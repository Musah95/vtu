# Register your models here.
from django.contrib import admin

from .models import LedgerEntry, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "is_locked", "updated_at")
    readonly_fields = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "wallet", "entry_type", "amount", "balance_after", "reference")
    list_filter = ("entry_type",)
    search_fields = ("reference", "wallet__user__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False