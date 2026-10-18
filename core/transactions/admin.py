from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "service", "destination", "amount", "status", "reference")
    list_filter = ("service", "status")
    search_fields = ("reference", "provider_reference", "destination", "user__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False