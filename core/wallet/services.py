from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from .models import LedgerEntry, ManualFunding, Wallet

class WalletError(Exception):
    pass


class InsufficientBalance(WalletError):
    pass


class WalletLocked(WalletError):
    pass


@transaction.atomic
def _apply(user, entry_type, amount, reference, description=""):
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    if amount <= 0:
        raise ValueError("Amount must be positive.")

    # Row lock: concurrent requests for this wallet queue up here.
    wallet = Wallet.objects.select_for_update().get(user=user)

    # Idempotency: same reference + type returns the original entry.
    existing = LedgerEntry.objects.filter(
        wallet=wallet, reference=reference, entry_type=entry_type
    ).first()
    if existing:
        return existing

    if wallet.is_locked and entry_type == LedgerEntry.Type.DEBIT:
        raise WalletLocked("Wallet is locked.")

    if entry_type == LedgerEntry.Type.DEBIT:
        if wallet.balance < amount:
            raise InsufficientBalance("Insufficient wallet balance.")
        wallet.balance -= amount
    else:
        wallet.balance += amount

    wallet.save(update_fields=["balance", "updated_at"])
    return LedgerEntry.objects.create(
        wallet=wallet,
        entry_type=entry_type,
        amount=amount,
        balance_after=wallet.balance,
        reference=reference,
        description=description,
    )


def credit(user, amount, reference, description=""):
    return _apply(user, LedgerEntry.Type.CREDIT, amount, reference, description)


def debit(user, amount, reference, description=""):
    return _apply(user, LedgerEntry.Type.DEBIT, amount, reference, description)

class ManualFundingError(Exception):
    pass


def max_manual_funding():
    return Decimal(str(getattr(settings, "MANUAL_FUNDING_MAX_AMOUNT", "500000")))


@transaction.atomic
def fund_manually(user, amount, admin_user, note):
    """
    An admin credits a user's wallet by hand. Goes through credit(), so the
    ledger records it, and writes an audit record of who did it and why.
    """
    note = (note or "").strip()
    if not note:
        raise ManualFundingError("A note explaining where the money came from is required.")
    try:
        amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ManualFundingError("Enter a valid amount.")
    if amount <= 0:
        raise ManualFundingError("The amount must be greater than zero.")
    if amount > max_manual_funding():
        raise ManualFundingError(
            f"The amount is above the per-action limit of {max_manual_funding()}."
        )
    if user.pk == admin_user.pk and not admin_user.is_superuser:
        raise ManualFundingError("You can't fund your own wallet.")

    wallet = Wallet.objects.get(user=user)
    record = ManualFunding.objects.create(
        wallet=wallet, funded_by=admin_user, amount=amount, note=note[:255]
    )
    credit(user, amount, f"manual-fund:{record.pk}", f"Manual funding: {note}"[:255])
    return record