from rest_framework.permissions import BasePermission
from .models import UserSubscription, SubscriptionPlan


class IsPremiumUser(BasePermission):
    """
    Permission that checks if user has an active premium subscription.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Check if user has active premium subscription
        active_subscription = UserSubscription.objects.filter(
            user=request.user,
            status='active'
        ).first()

        if not active_subscription:
            return False

        # Check if plan is premium (not free)
        return active_subscription.plan.tier != 'free'


class HasLoanLimit(BasePermission):
    """
    Permission that checks if user hasn't exceeded their loan limit.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Get user's active subscription
        subscription = UserSubscription.objects.filter(
            user=request.user,
            status='active'
        ).first()

        if not subscription:
            # Free tier - check loan count
            loan_count = request.user.loans.filter(is_active=True).count()
            return loan_count < 3  # Free tier limit

        # Premium tier - check against plan limits
        loan_count = request.user.loans.filter(is_active=True).count()
        return loan_count < subscription.plan.max_loans


class HasPlanLimit(BasePermission):
    """
    Permission that checks if user hasn't exceeded their plan limit.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Get user's active subscription
        subscription = UserSubscription.objects.filter(
            user=request.user,
            status='active'
        ).first()

        if not subscription:
            # Free tier - check plan count
            plan_count = request.user.debt_plans.filter(status__in=['active', 'draft']).count()
            return plan_count < 1  # Free tier limit

        # Premium tier - check against plan limits
        plan_count = request.user.debt_plans.filter(status__in=['active', 'draft']).count()
        return plan_count < subscription.plan.max_plans


class CanExportPlans(BasePermission):
    """
    Permission for exporting debt plans (premium feature).
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Get user's active subscription
        subscription = UserSubscription.objects.filter(
            user=request.user,
            status='active'
        ).first()

        if not subscription:
            return False  # Free users cannot export

        # Check if plan allows exports (Pro and Premium)
        return subscription.plan.tier in ['pro', 'premium']


class CanComparePlans(BasePermission):
    """
    Permission for comparing multiple debt plans (premium feature).
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Get user's active subscription
        subscription = UserSubscription.objects.filter(
            user=request.user,
            status='active'
        ).first()

        if not subscription:
            return False  # Free users cannot compare plans

        # Check if plan allows comparison (Pro and Premium)
        return subscription.plan.tier in ['pro', 'premium']