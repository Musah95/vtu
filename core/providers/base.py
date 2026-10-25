from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"      # provider DEFINITELY did not deliver
    UNKNOWN = "unknown"    # timeout / ambiguous: may or may not have delivered


@dataclass
class PurchaseRequest:
    service: str
    request_id: str        # our unique id for this attempt, used for requery
    destination: str
    amount: Decimal
    extra: dict = field(default_factory=dict)


@dataclass
class ProviderResult:
    status: ProviderStatus
    provider_reference: str = ""
    message: str = ""
    raw: dict = field(default_factory=dict)


class ProviderAdapter(ABC):
    name: str = ""

    @abstractmethod
    def purchase(self, request: PurchaseRequest) -> ProviderResult: ...

    @abstractmethod
    def requery(self, request_id: str) -> ProviderResult: ...

    def balance(self) -> Decimal:
        raise NotImplementedError

    def lookup(self, request: LookupRequest) -> LookupResult:
        """Optional: vendors that can verify an account implement this."""
        raise NotImplementedError

class LookupStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"          # the vendor clearly says this account doesn't exist
    UNAVAILABLE = "unavailable"  # timeout or vendor down: we don't know


@dataclass
class LookupRequest:
    service: str
    destination: str             # smartcard, meter number, ...
    extra: dict = field(default_factory=dict)


@dataclass
class LookupResult:
    status: LookupStatus
    customer_name: str = ""
    details: dict = field(default_factory=dict)
    message: str = ""
    raw: dict = field(default_factory=dict)