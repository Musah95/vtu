from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.common.exceptions import ServiceError
from core.transactions.api import OrderDetailViewBase, PurchaseViewBase

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
        items = []
        for p in plans:
            try:
                price = price_for(request.user, p)
            except ServiceError:
                continue          # misconfigured price: hide the plan, keep the list working
            items.append({
                "id": p.pk, "network": p.network, "category": p.category,
                "name": p.name, "validity": p.validity, "price": str(price),
            })
        return Response(items)


class PurchaseView(PurchaseViewBase):
    service = SERVICE
    serializer_class = PurchaseSerializer
    order_serializer = OrderSerializer

    def run_purchase(self, user, source, **data):
        return purchase(user, source=source, **data)


class OrderDetailView(OrderDetailViewBase):
    service = SERVICE
    order_serializer = OrderSerializer