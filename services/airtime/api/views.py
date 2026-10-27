from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.transactions.api import OrderDetailViewBase, PurchaseViewBase

from ..models import Network
from ..services import SERVICE, purchase
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


class PurchaseView(PurchaseViewBase):
    service = SERVICE
    serializer_class = PurchaseSerializer
    order_serializer = OrderSerializer

    def run_purchase(self, user, source, **data):
        return purchase(user, source=source, **data)


class OrderDetailView(OrderDetailViewBase):
    service = SERVICE
    order_serializer = OrderSerializer