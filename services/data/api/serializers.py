from rest_framework import serializers

from core.transactions.models import Transaction


class PurchaseSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(min_value=1)
    phone = serializers.CharField(max_length=20)
    reference = serializers.CharField(max_length=100, required=False)


class OrderSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="destination")
    network = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    validity = serializers.SerializerMethodField()
    amount_charged = serializers.DecimalField(source="amount", max_digits=14, decimal_places=2)

    class Meta:
        model = Transaction
        fields = [
            "reference", "status", "phone", "network", "plan_name", "validity",
            "amount_charged", "failure_reason", "created_at", "completed_at",
        ]

    def get_network(self, obj):
        return obj.payload.get("network")

    def get_plan_name(self, obj):
        return obj.payload.get("plan_name")

    def get_validity(self, obj):
        return obj.payload.get("validity")