from rest_framework import serializers
from .models import DebtPlan, PlanProgress


class DebtPlanSerializer(serializers.ModelSerializer):
    """Serializer for DebtPlan model."""

    loans_count = serializers.SerializerMethodField()
    is_calculated = serializers.SerializerMethodField()

    class Meta:
        model = DebtPlan
        fields = [
            'id', 'user', 'name', 'method', 'extra_payment', 'consolidation_rate',
            'consolidation_term', 'total_debt', 'total_interest_saved', 'payoff_months',
            'total_payments', 'status', 'is_active', 'plan_data', 'loans_count',
            'is_calculated', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'total_debt', 'total_interest_saved', 'payoff_months',
            'total_payments', 'plan_data', 'loans_count', 'is_calculated', 'created_at', 'updated_at'
        ]

    def get_loans_count(self, obj):
        """Get the number of loans associated with this plan."""
        return obj.loans.count()

    def get_is_calculated(self, obj):
        """Check if the plan has been calculated."""
        return bool(obj.plan_data)

    def create(self, validated_data):
        """Create a debt plan for the authenticated user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        """Validate consolidation-specific fields."""
        method = data.get('method')
        if method == 'consolidation':
            if not data.get('consolidation_rate'):
                raise serializers.ValidationError({
                    'consolidation_rate': 'This field is required for consolidation plans.'
                })
            if not data.get('consolidation_term'):
                raise serializers.ValidationError({
                    'consolidation_term': 'This field is required for consolidation plans.'
                })
        return data


class DebtPlanCalculateSerializer(serializers.Serializer):
    """Serializer for debt plan calculation request."""

    method = serializers.ChoiceField(choices=DebtPlan.METHOD_CHOICES)
    extra_payment = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=0, min_value=0
    )
    consolidation_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, min_value=0, max_value=100
    )
    consolidation_term = serializers.IntegerField(required=False, min_value=1, max_value=360)

    def validate(self, data):
        """Validate consolidation-specific fields."""
        method = data.get('method')
        if method == 'consolidation':
            if 'consolidation_rate' not in data:
                raise serializers.ValidationError({
                    'consolidation_rate': 'This field is required for consolidation plans.'
                })
            if 'consolidation_term' not in data:
                raise serializers.ValidationError({
                    'consolidation_term': 'This field is required for consolidation plans.'
                })
        return data


class PlanProgressSerializer(serializers.ModelSerializer):
    """Serializer for PlanProgress model."""

    class Meta:
        model = PlanProgress
        fields = [
            'id', 'plan', 'month', 'actual_payment', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        """Create progress entry and ensure it belongs to user's plan."""
        plan = validated_data['plan']
        if plan.user != self.context['request'].user:
            raise serializers.ValidationError("You can only add progress to your own plans.")
        return super().create(validated_data)


class DebtPlanSummarySerializer(serializers.Serializer):
    """Serializer for debt plan summary."""

    total_plans = serializers.IntegerField()
    active_plans = serializers.IntegerField()
    completed_plans = serializers.IntegerField()
    total_debt_managed = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_interest_saved = serializers.DecimalField(max_digits=12, decimal_places=2)