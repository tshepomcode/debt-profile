from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid


class SubscriptionPlan(models.Model):
    """Available subscription plans."""

    PLAN_TYPES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('premium', 'Premium'),
    ]

    INTERVAL_CHOICES = [
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default='month')

    # Pricing
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Price in USD"
    )
    stripe_price_id = models.CharField(max_length=100, blank=True, help_text="Stripe Price ID")

    # Features
    max_loans = models.PositiveIntegerField(default=10, help_text="Maximum number of loans allowed")
    can_export = models.BooleanField(default=False, help_text="Can export plans to PDF")
    can_compare = models.BooleanField(default=False, help_text="Can compare multiple plans")
    advanced_analytics = models.BooleanField(default=False, help_text="Access to advanced analytics")
    priority_support = models.BooleanField(default=False, help_text="Priority customer support")
    api_access = models.BooleanField(default=False, help_text="API access for integrations")

    # Status
    is_active = models.BooleanField(default=True, help_text="Whether this plan is available for purchase")
    is_popular = models.BooleanField(default=False, help_text="Mark as popular plan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f"{self.name} - ${self.price}/{self.interval}"


class UserSubscription(models.Model):
    """User's current subscription."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
        ('incomplete', 'Incomplete'),
        ('trialing', 'Trialing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)

    # Stripe data
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_price_id = models.CharField(max_length=100, blank=True)

    # Subscription details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Trial
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"

    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status in ['active', 'trialing']

    @property
    def is_trial_active(self):
        """Check if trial is currently active."""
        if not self.trial_end:
            return False
        from django.utils import timezone
        return timezone.now() <= self.trial_end

    @property
    def days_until_trial_end(self):
        """Get days remaining in trial."""
        if not self.is_trial_active:
            return 0
        from django.utils import timezone
        delta = self.trial_end - timezone.now()
        return max(0, delta.days)


class Payment(models.Model):
    """Record of payments made by users."""

    PAYMENT_TYPES = [
        ('subscription', 'Subscription'),
        ('one_time', 'One-time Purchase'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )

    # Payment details
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default='usd')

    # Stripe data
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True)

    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(blank=True, help_text="Description of the payment")
    failure_reason = models.TextField(blank=True, help_text="Reason for payment failure")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"{self.user.username} - ${self.amount} ({self.status})"


class WaitingList(models.Model):
    """Waiting list for early access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    interest = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free basic calculator'),
            ('pro', 'Pro features'),
            ('premium', 'Premium features'),
            ('business', 'Business solutions'),
        ],
        default='free'
    )
    signup_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_notified = models.BooleanField(default=False, help_text="Whether user has been notified of launch")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Waiting List'
        verbose_name_plural = 'Waiting List'

    def __str__(self):
        return f"{self.name} ({self.email})"
