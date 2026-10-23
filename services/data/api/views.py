from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.common.exceptions import ServiceError
from core.transactions.models import S, Transaction

from ..models import DataPlan
from ..services import SERVICE, price_for, purchase
from .serializers import OrderSerializer, PurchaseSerializer


class PlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = DataPlan.objects.filter(is_active=True).prefetch_related("prices")
        network = request.query_params.get("network")
        if network:
            plans = plans.filter(network=network)
        return Response([
            {
                "id": p.pk, "network": p.network, "category": p.category,
                "name": p.name, "validity": p.validity,
                "price": str(price_for(request.user, p)),   # price for THIS user's role
            }
            for p in plans
        ])


class PurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            txn, created = purchase(request.user, **serializer.validated_data)
        except ServiceError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=400)

        order = OrderSerializer(txn).data
        if not created:
            return Response(order, status=200)          # repeated reference
        if txn.status == S.FAILED:                       # wallet refused the debit
            return Response(
                {"code": "PURCHASE_REJECTED", "detail": txn.failure_reason, "order": order},
                status=402,
            )
        return Response(order, status=201)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        txn = get_object_or_404(
            Transaction, user=request.user, service=SERVICE, reference=reference
        )
        return Response(OrderSerializer(txn).data)