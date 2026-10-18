from decimal import Decimal

from django.db import transaction

from .models import LedgerEntry, Wallet


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