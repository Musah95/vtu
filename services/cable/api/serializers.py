from rest_framework import serializers

from core.transactions.models import Transaction

from ..models import Operator


class VerifySerializer(serializers.Serializer):
    operator = serializers.ChoiceField(choices=Operator.choices)
    smartcard = serializers.CharField(max_length=20)


class PurchaseSerializer(serializers.Serializer):
    verification_id = serializers.UUIDField()
    package_id = serializers.IntegerField(min_value=1)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    reference = serializers.CharField(max_length=100, required=False)


class OrderSerializer(serializers.ModelSerializer):
    smartcard = serializers.CharField(source="destination")
    operator = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()
    validity = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    amount_charged = serializers.DecimalField(source="amount", max_digits=14, decimal_places=2)

    class Meta:
        model = Transaction
        fields = [
            "reference", "status", "smartcard", "operator", "package_name", "validity",
            "customer_name", "amount_charged", "failure_reason", "created_at", "completed_at",
        ]

    def get_operator(self, obj):
        return obj.payload.get("operator")

    def get_package_name(self, obj):
        return obj.payload.get("package_name")

    def get_validity(self, obj):
        return obj.payload.get("validity")

    def get_customer_name(self, obj):
        return obj.payload.get("customer_name")