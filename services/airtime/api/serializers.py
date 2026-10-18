from decimal import Decimal

from rest_framework import serializers

from core.transactions.models import Transaction


class PurchaseSerializer(serializers.Serializer):
    network = serializers.CharField(max_length=20)
    phone = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("1"))
    reference = serializers.CharField(max_length=100, required=False)


class OrderSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="destination")
    network = serializers.SerializerMethodField()
    face_value = serializers.SerializerMethodField()
    amount_charged = serializers.DecimalField(source="amount", max_digits=14, decimal_places=2)

    class Meta:
        model = Transaction
        fields = [
            "reference", "status", "phone", "network", "face_value",
            "amount_charged", "failure_reason", "created_at", "completed_at",
        ]

    def get_network(self, obj):
        return obj.payload.get("network")

    def get_face_value(self, obj):
        return obj.payload.get("face_value")