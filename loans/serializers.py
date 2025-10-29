from rest_framework import serializers
from .models import Loan


class LoanSerializer(serializers.ModelSerializer):
    """Serializer for Loan model with validation."""

    monthly_interest_rate = serializers.ReadOnlyField()
    estimated_payoff_months = serializers.ReadOnlyField()

    class Meta:
        model = Loan
        fields = [
            'id', 'user', 'name', 'balance', 'interest_rate', 'monthly_interest_rate',
            'minimum_payment', 'estimated_payoff_months', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'monthly_interest_rate', 'estimated_payoff_months', 'created_at', 'updated_at']

    def create(self, validated_data):
        """Create a loan for the authenticated user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_balance(self, value):
        """Validate balance is positive."""
        if value <= 0:
            raise serializers.ValidationError("Balance must be greater than zero.")
        return value

    def validate_interest_rate(self, value):
        """Validate interest rate is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Interest rate cannot be negative.")
        return value

    def validate_minimum_payment(self, value):
        """Validate minimum payment is positive."""
        if value <= 0:
            raise serializers.ValidationError("Minimum payment must be greater than zero.")
        return value


class LoanSummarySerializer(serializers.Serializer):
    """Serializer for loan summary statistics."""

    total_loans = serializers.IntegerField()
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_minimum_payments = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)