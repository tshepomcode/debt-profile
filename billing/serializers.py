from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription, Payment, WaitingList


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan model."""

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'plan_type', 'interval', 'price', 'stripe_price_id',
            'max_loans', 'can_export', 'can_compare', 'advanced_analytics',
            'priority_support', 'api_access', 'is_active', 'is_popular',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for UserSubscription model."""

    plan_name = serializers.CharField(source='plan.name', read_only=True)
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'user', 'plan', 'plan_name', 'status', 'current_period_start',
            'current_period_end', 'cancel_at_period_end', 'days_remaining',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'current_period_start', 'current_period_end',
            'days_remaining', 'created_at', 'updated_at'
        ]

    def get_days_remaining(self, obj):
        """Calculate days remaining in current subscription period."""
        if obj.current_period_end:
            from django.utils import timezone
            remaining = obj.current_period_end - timezone.now().date()
            return max(0, remaining.days)
        return 0


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""

    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'subscription', 'payment_type', 'amount', 'currency',
            'status', 'stripe_payment_intent_id', 'stripe_charge_id', 'description',
            'failure_reason', 'created_at', 'updated_at', 'paid_at'
        ]
        read_only_fields = [
            'id', 'user', 'stripe_payment_intent_id', 'stripe_charge_id',
            'created_at', 'updated_at', 'paid_at'
        ]


class WaitingListSerializer(serializers.ModelSerializer):
    """Serializer for WaitingList model."""

    class Meta:
        model = WaitingList
        fields = [
            'id', 'email', 'name', 'interest', 'signup_ip', 'user_agent',
            'is_notified', 'created_at'
        ]
        read_only_fields = ['id', 'signup_ip', 'user_agent', 'is_notified', 'created_at']

    def create(self, validated_data):
        """Create waiting list entry, handling duplicates."""
        email = validated_data.get('email')
        if WaitingList.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already on the waiting list.")
        return super().create(validated_data)


class BillingSummarySerializer(serializers.Serializer):
    """Serializer for billing summary statistics."""

    current_plan = serializers.CharField()
    subscription_status = serializers.CharField()
    next_billing_date = serializers.DateField()
    total_payments = serializers.DecimalField(max_digits=10, decimal_places=2)
    waiting_list_count = serializers.IntegerField()