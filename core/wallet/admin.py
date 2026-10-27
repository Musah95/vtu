from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm

from .models import LedgerEntry, ManualFunding, Wallet
from .services import ManualFundingError, fund_manually


class FundActionForm(ActionForm):
    """Adds amount and note boxes next to the action dropdown."""
    amount = forms.CharField(
        required=False, label="Amount (NGN)",
        widget=forms.TextInput(attrs={"size": 12, "placeholder": "e.g. 5000"}),
    )
    note = forms.CharField(
        required=False, label="Note",
        widget=forms.TextInput(attrs={
            "size": 60,
            "placeholder": "Source of funds, e.g. bank transfer ref 123456, checked on bank dashboard",
        }),
    )


class ManualFundingInline(admin.TabularInline):
    model = ManualFunding
    extra = 0
    fields = ("created_at", "funded_by", "amount", "note")
    readonly_fields = ("created_at", "funded_by", "amount", "note")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "is_locked", "updated_at")
    readonly_fields = ("user", "balance", "created_at", "updated_at")
    search_fields = ("user__username", "user__email")
    inlines = [ManualFundingInline]
    action_form = FundActionForm
    actions = ["credit_wallet"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_fund_permission(self, request):
        return request.user.has_perm("wallet.fund_wallet")

    @admin.action(description="Fund this wallet (manual credit)", permissions=["fund"])
    def credit_wallet(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one wallet.", messages.ERROR)
            return
        try:
            amount = Decimal(request.POST.get("amount", "").strip())
        except InvalidOperation:
            self.message_user(
                request, "Enter a valid amount, then run the action again. Nothing was changed.",
                messages.ERROR,
            )
            return

        wallet = queryset.get()
        try:
            record = fund_manually(wallet.user, amount, request.user, request.POST.get("note", ""))
        except ManualFundingError as exc:
            self.message_user(request, f"{exc} Nothing was changed.", messages.ERROR)
            return

        wallet.refresh_from_db()
        self.message_user(
            request,
            f"Credited NGN {record.amount} to {wallet.user}. New balance: NGN {wallet.balance}.",
            messages.SUCCESS,
        )


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


@admin.register(ManualFunding)
class ManualFundingAdmin(admin.ModelAdmin):
    list_display = ("created_at", "wallet", "amount", "funded_by", "note")
    search_fields = ("wallet__user__username", "funded_by__username", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False