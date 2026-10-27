from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.common.exceptions import ServiceError

from .models import S, Transaction


def source_for(request):
    """'api:<key id>' for API-key calls, otherwise 'web'."""
    key_id = getattr(request.auth, "key_id", None)
    return f"api:{key_id}" if key_id else "web"


class PurchaseViewBase(APIView):
    """The shared purchase endpoint. Each service sets four things."""
    permission_classes = [IsAuthenticated]
    service = None               # "airtime", "data", ...
    serializer_class = None      # validates the request body
    order_serializer = None      # shapes the response

    def run_purchase(self, user, source, **data):
        raise NotImplementedError

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # A retry with a reference we already hold gets the original order back,
        # before any check that could have changed in the meantime.
        reference = data.get("reference")
        if reference:
            existing = Transaction.objects.filter(
                user=request.user, service=self.service, reference=reference
            ).first()
            if existing:
                return Response(self.order_serializer(existing).data, status=200)

        try:
            txn, created = self.run_purchase(request.user, source_for(request), **data)
        except ServiceError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=400)

        order = self.order_serializer(txn).data
        if not created:
            return Response(order, status=200)           # repeated reference
        if txn.status == S.FAILED:                        # wallet refused the debit
            return Response(
                {"code": "PURCHASE_REJECTED", "detail": txn.failure_reason, "order": order},
                status=402,
            )
        return Response(order, status=201)


class OrderDetailViewBase(APIView):
    permission_classes = [IsAuthenticated]
    service = None
    order_serializer = None

    def get(self, request, reference):
        txn = get_object_or_404(
            Transaction, user=request.user, service=self.service, reference=reference
        )
        return Response(self.order_serializer(txn).data)