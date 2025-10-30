from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Loan(models.Model):
    """Model representing a user's debt/loan."""

    LOAN_TYPES = [
        ('credit_card', 'Credit Card'),
        ('personal_loan', 'Personal Loan'),
        ('student_loan', 'Student Loan'),
        ('auto_loan', 'Auto Loan'),
        ('mortgage', 'Mortgage'),
        ('medical_debt', 'Medical Debt'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    name = models.CharField(max_length=100, help_text="Name or description of the loan")
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPES, default='other')
    creditor = models.CharField(max_length=100, blank=True, help_text="Name of the creditor/lender")

    # Financial details
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Current outstanding balance"
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Annual interest rate (APR) in percent"
    )
    minimum_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Minimum monthly payment required"
    )

    # Optional fields
    original_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original loan amount (if different from current balance)"
    )
    term_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Original term in months (if applicable)"
    )
    remaining_term_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Remaining term in months"
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Monthly due date"
    )

    # Metadata
    is_active = models.BooleanField(default=True, help_text="Whether this loan is still active")
    notes = models.TextField(blank=True, help_text="Additional notes about the loan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'

    def __str__(self):
        return f"{self.user.username} - {self.name} (${self.balance})"

    @property
    def monthly_interest_rate(self):
        """Calculate monthly interest rate from annual rate."""
        return self.interest_rate / 100 / 12

    @property
    def estimated_payoff_months(self):
        """Estimate months to pay off with minimum payments (simplified calculation)."""
        if self.minimum_payment <= 0:
            return None

        # Simplified calculation - doesn't account for compound interest properly
        # For accurate calculations, use the debt plan algorithms
        balance = float(self.balance)
        monthly_rate = float(self.monthly_interest_rate)
        min_payment = float(self.minimum_payment)

        if monthly_rate == 0:
            return balance / min_payment

        # Approximate using formula for loan amortization
        try:
            months = - (balance * monthly_rate) / (min_payment * (1 - (1 + monthly_rate) ** (-balance / min_payment)))
            return max(1, round(months))
        except (ZeroDivisionError, ValueError):
            return None

    @property
    def total_interest_paid(self):
        """Calculate total interest that would be paid with minimum payments."""
        months = self.estimated_payoff_months
        if months is None:
            return None

        total_paid = months * float(self.minimum_payment)
        return total_paid - float(self.balance)
