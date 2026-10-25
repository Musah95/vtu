from ..base import LookupResult, LookupStatus, ProviderAdapter, ProviderResult, ProviderStatus
from ..registry import register


@register
class MockProvider(ProviderAdapter):
    """
    Destination ending 0000  -> definitive failure
    Destination ending 9999  -> timeout (UNKNOWN); requery later says it was delivered
    Anything else            -> success
    """
    name = "mock"
    _delivered = set()

    def purchase(self, request):
        if request.destination.endswith("0000"):
            return ProviderResult(
                ProviderStatus.FAILED, message="Mock: request rejected",
                raw={"mock": "rejected"},
            )
        if request.destination.endswith("9999"):
            type(self)._delivered.add(request.request_id)
            return ProviderResult(
                ProviderStatus.UNKNOWN, message="Mock: timeout",
                raw={"mock": "timeout"},
            )
        return ProviderResult(
            ProviderStatus.SUCCESS,
            provider_reference=f"MOCK-{request.request_id}",
            raw={"mock": "ok"},
        )

    def requery(self, request_id):
        if request_id in type(self)._delivered:
            return ProviderResult(
                ProviderStatus.SUCCESS, provider_reference=f"MOCK-{request_id}",
                raw={"mock": "delivered"},
            )
        return ProviderResult(ProviderStatus.FAILED, message="Mock: not found")

    def lookup(self, request):
        number = request.destination
        if number.endswith("0000"):
            return LookupResult(LookupStatus.INVALID, message="Mock: account not found")
        if number.endswith("9999"):
            return LookupResult(LookupStatus.UNAVAILABLE, message="Mock: vendor timeout")
        return LookupResult(
            LookupStatus.VALID, customer_name="MOCK CUSTOMER",
            details={"current_plan": "Mock Compact", "status": "active"},
            raw={"mock": "ok"},
        )