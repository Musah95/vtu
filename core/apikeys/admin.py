from django.contrib import admin, messages

from .models import ApiKey
from .services import generate_credentials, revoke_key

READONLY = ("key_id", "created_at", "last_used_at", "revoked_at")


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("key_id", "user", "label", "created_at", "last_used_at", "active")
    search_fields = ("key_id", "label", "user__username")
    actions = ["revoke_selected"]

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("user", "label")
        return ("user", "label") + READONLY

    def get_readonly_fields(self, request, obj=None):
        return (READONLY + ("user",)) if obj else READONLY

    @admin.display(boolean=True, description="Active")
    def active(self, obj):
        return obj.is_active

    def has_delete_permission(self, request, obj=None):
        return False                           # revoke instead, so history is kept

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        key_id, secret, secret_hash = generate_credentials()
        obj.key_id = key_id
        obj.secret_hash = secret_hash
        super().save_model(request, obj, form, change)
        self.message_user(
            request,
            f"Key created. Key ID: {key_id}   Secret: {secret}   "
            "Copy the secret NOW: it is never shown again.",
            messages.WARNING,
        )

    @admin.action(description="Revoke selected API keys")
    def revoke_selected(self, request, queryset):
        for api_key in queryset:
            revoke_key(api_key)
        self.message_user(request, f"{queryset.count()} key(s) revoked.", messages.SUCCESS)