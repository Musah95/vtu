from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.common.exceptions import ServiceError
from core.transactions.api import OrderDetailViewBase, PurchaseViewBase

from ..models import CablePackage
from ..services import SERVICE, price_for, purchase, verify
from .serializers import OrderSerializer, PurchaseSerializer, VerifySerializer


class PackageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        packages = CablePackage.objects.filter(is_active=True).prefetch_related("prices")
        operator = request.query_params.get("operator")
        if operator:
            packages = packages.filter(operator=operator)
        items = []
        for p in packages:
            try:
                price = price_for(request.user, p)
            except ServiceError:
                continue          # misconfigured price: hide the package, keep the list working
            items.append({
                "id": p.pk, "operator": p.operator, "name": p.name,
                "validity": p.validity, "price": str(price),
            })
        return Response(items)


class VerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "cable_verify"

    def post(self, request):
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            v = verify(request.user, **serializer.validated_data)
        except ServiceError as exc:
            code = 503 if exc.code == "VERIFICATION_UNAVAILABLE" else 400
            return Response({"code": exc.code, "detail": exc.message}, status=code)
        return Response({
            "verification_id": str(v.pk),
            "operator": v.operator,
            "smartcard": v.smartcard,
            "customer_name": v.customer_name,
            "details": v.details,
            "expires_at": v.expires_at,
        })


class PurchaseView(PurchaseViewBase):
    service = SERVICE
    serializer_class = PurchaseSerializer
    order_serializer = OrderSerializer

    def run_purchase(self, user, source, **data):
        return purchase(user, source=source, **data)


class OrderDetailView(OrderDetailViewBase):
    service = SERVICE
    order_serializer = OrderSerializer