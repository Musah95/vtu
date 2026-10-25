from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm

from .models import ManualResolution, Transaction
from .services import ManualResolutionError, resolve_manually

MAX_BULK = 25


class ResolveActionForm(ActionForm):
    """Adds a note box next to the action dropdown."""
    note = forms.CharField(
        required=False, max_length=255, label="Note",
        widget=forms.TextInput(attrs={
            "size": 60,
            "placeholder": "Why? e.g. vendor confirmed not delivered, ticket #123",
        }),
    )


class ManualResolutionInline(admin.TabularInline):
    model = ManualResolution
    extra = 0
    fields = ("created_at", "resolved_by", "outcome", "note")
    readonly_fields = ("created_at", "resolved_by", "outcome", "note")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "user", "service", "destination", "amount",
        "status", "reference", "request_id",
    )
    list_filter = ("service", "status")
    search_fields = ("reference", "provider_reference", "destination", "user__username")
    inlines = [ManualResolutionInline]
    action_form = ResolveActionForm
    actions = ["mark_failed_and_refund", "mark_successful"]

    @admin.display(description="Vendor request id")
    def request_id(self, obj):
        return f"txn-{obj.pk}"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_resolve_permission(self, request):
        return request.user.has_perm("transactions.resolve_transaction")

    @admin.action(
        description="Resolve: mark FAILED and refund the wallet",
        permissions=["resolve"],
    )
    def mark_failed_and_refund(self, request, queryset):
        self._resolve(request, queryset, ManualResolution.Outcome.FAILED)

    @admin.action(
        description="Resolve: mark SUCCESSFUL (vendor delivered)",
        permissions=["resolve"],
    )
    def mark_successful(self, request, queryset):
        self._resolve(request, queryset, ManualResolution.Outcome.SUCCESS)

    def _resolve(self, request, queryset, outcome):
        note = request.POST.get("note", "").strip()
        if not note:
            self.message_user(
                request,
                "Type a note explaining why, then run the action again. Nothing was changed.",
                messages.ERROR,
            )
            return
        if queryset.count() > MAX_BULK:
            self.message_user(
                request, f"Select at most {MAX_BULK} transactions at a time.", messages.ERROR
            )
            return

        done = 0
        for txn in queryset:
            try:
                resolve_manually(txn.pk, outcome, request.user, note)
                done += 1
            except ManualResolutionError as exc:
                self.message_user(request, f"{txn.reference}: {exc}", messages.ERROR)
        if done:
            self.message_user(request, f"{done} transaction(s) resolved.", messages.SUCCESS)