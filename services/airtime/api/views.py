from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.transactions.models import S, Transaction

from ..models import Network
from ..services import SERVICE, AirtimeError, purchase
from .serializers import OrderSerializer, PurchaseSerializer


class NetworkListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        networks = Network.objects.filter(is_active=True)
        return Response([
            {"code": n.code, "name": n.name,
             "min_amount": n.min_amount, "max_amount": n.max_amount}
            for n in networks
        ])


class PurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            txn, created = purchase(request.user, **serializer.validated_data)
        except AirtimeError as exc:
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