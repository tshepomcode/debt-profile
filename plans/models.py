from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from loans.models import Loan
import uuid
import json


class DebtPlan(models.Model):
    """Model representing a debt reduction plan for a user."""

    METHOD_CHOICES = [
        ('snowball', 'Debt Snowball'),
        ('avalanche', 'Debt Avalanche'),
        ('consolidation', 'Debt Consolidation'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debt_plans')
    name = models.CharField(max_length=100, help_text="Name for this debt plan")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, help_text="Debt reduction method")

    # Plan configuration
    extra_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Extra monthly payment amount"
    )

    # For consolidation plans
    consolidation_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MinValueValidator(100)],
        help_text="Consolidated loan interest rate (for consolidation method)"
    )
    consolidation_term = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Consolidated loan term in months"
    )

    # Plan results
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_interest_saved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payoff_months = models.PositiveIntegerField(default=0, help_text="Estimated months to pay off all debt")
    total_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_active = models.BooleanField(default=False, help_text="Whether this is the user's active plan")
    plan_data = models.JSONField(default=dict, help_text="Detailed plan calculation data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Debt Plan'
        verbose_name_plural = 'Debt Plans'

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.get_method_display()})"

    def save(self, *args, **kwargs):
        # Ensure only one active plan per user
        if self.is_active:
            DebtPlan.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def loans(self):
        """Get loans associated with this plan."""
        return Loan.objects.filter(
            user=self.user,
            is_active=True
        ).order_by('balance' if self.method == 'snowball' else '-interest_rate')

    def calculate_plan(self):
        """Calculate the debt reduction plan based on the selected method."""
        loans = list(self.loans)
        if not loans:
            return self._empty_plan_data()

        if self.method == 'snowball':
            return self._calculate_snowball(loans)
        elif self.method == 'avalanche':
            return self._calculate_avalanche(loans)
        elif self.method == 'consolidation':
            return self._calculate_consolidation(loans)
        else:
            return self._empty_plan_data()

    def _empty_plan_data(self):
        """Return empty plan data structure."""
        return {
            'total_debt': 0,
            'total_interest': 0,
            'payoff_months': 0,
            'monthly_payment': 0,
            'schedule': [],
            'summary': {}
        }

    def _calculate_snowball(self, loans):
        """Calculate Debt Snowball plan (pay smallest balances first)."""
        # Create working copies to avoid modifying original loan objects
        loan_data = []
        for loan in loans:
            loan_data.append({
                'id': loan.id,
                'balance': float(loan.balance),
                'minimum_payment': float(loan.minimum_payment),
                'monthly_interest_rate': float(loan.monthly_interest_rate),
                'name': loan.name
            })

        # Sort by balance ascending (smallest first)
        loan_data.sort(key=lambda x: x['balance'])

        total_debt = sum(loan['balance'] for loan in loan_data)
        total_interest = 0
        monthly_payment = sum(loan['minimum_payment'] for loan in loan_data) + float(self.extra_payment)

        schedule = []
        current_month = 0
        remaining_loans = loan_data.copy()

        while remaining_loans and current_month < 600:  # Max 50 years
            current_month += 1
            month_data = {
                'month': current_month,
                'payments': {},
                'total_payment': 0,
                'remaining_balance': 0
            }

            # Calculate payments for this month
            available_payment = monthly_payment

            # Process loans in snowball order (smallest balance first)
            for loan in remaining_loans[:]:
                balance = loan['balance']

                if balance <= 0:
                    remaining_loans.remove(loan)
                    continue

                # Calculate minimum payment for this loan
                min_payment = loan['minimum_payment']

                # Pay minimum payment first
                payment = min(min_payment, balance)

                # Apply any remaining payment as extra towards this loan
                if available_payment > payment:
                    extra_available = available_payment - payment
                    extra_to_loan = min(extra_available, balance - payment)
                    payment += extra_to_loan
                    available_payment -= payment
                else:
                    # Not enough for minimum, pay what's available
                    payment = min(available_payment, balance)
                    available_payment = 0

                # Calculate interest for this month
                monthly_rate = loan['monthly_interest_rate']
                interest = balance * monthly_rate
                total_interest += interest

                # Update balance: add interest, subtract payment
                loan['balance'] = balance + interest - payment

                month_data['payments'][str(loan['id'])] = {
                    'payment': round(payment, 2),
                    'interest': round(interest, 2),
                    'balance': round(max(0, loan['balance']), 2)
                }
                month_data['total_payment'] += payment

                # Remove loan if paid off
                if loan['balance'] <= 0.01:  # Account for floating point precision
                    remaining_loans.remove(loan)

            month_data['remaining_balance'] = round(sum(loan['balance'] for loan in remaining_loans), 2)
            schedule.append(month_data)

            if not remaining_loans:
                break

        return {
            'total_debt': round(total_debt, 2),
            'total_interest': round(total_interest, 2),
            'payoff_months': current_month,
            'monthly_payment': round(monthly_payment, 2),
            'schedule': schedule,
            'summary': {
                'method': 'snowball',
                'loans_paid_off': len(loans) - len(remaining_loans),
                'remaining_loans': len(remaining_loans),
                'total_payments': round(total_debt + total_interest, 2)
            }
        }

    def _calculate_avalanche(self, loans):
        """Calculate Debt Avalanche plan (pay highest interest first)."""
        # Create working copies to avoid modifying original loan objects
        loan_data = []
        for loan in loans:
            loan_data.append({
                'id': loan.id,
                'balance': float(loan.balance),
                'minimum_payment': float(loan.minimum_payment),
                'monthly_interest_rate': float(loan.monthly_interest_rate),
                'name': loan.name
            })

        # Sort by interest rate descending (highest first)
        loan_data.sort(key=lambda x: x['monthly_interest_rate'], reverse=True)

        total_debt = sum(loan['balance'] for loan in loan_data)
        total_interest = 0
        monthly_payment = sum(loan['minimum_payment'] for loan in loan_data) + float(self.extra_payment)

        schedule = []
        current_month = 0
        remaining_loans = loan_data.copy()

        while remaining_loans and current_month < 600:  # Max 50 years
            current_month += 1
            month_data = {
                'month': current_month,
                'payments': {},
                'total_payment': 0,
                'remaining_balance': 0
            }

            # Calculate payments for this month
            available_payment = monthly_payment

            # Process loans in avalanche order (highest interest first)
            for loan in remaining_loans[:]:
                balance = loan['balance']

                if balance <= 0:
                    remaining_loans.remove(loan)
                    continue

                # Calculate minimum payment for this loan
                min_payment = loan['minimum_payment']

                # Pay minimum payment first
                payment = min(min_payment, balance)

                # Apply any remaining payment as extra towards this loan
                if available_payment > payment:
                    extra_available = available_payment - payment
                    extra_to_loan = min(extra_available, balance - payment)
                    payment += extra_to_loan
                    available_payment -= payment
                else:
                    # Not enough for minimum, pay what's available
                    payment = min(available_payment, balance)
                    available_payment = 0

                # Calculate interest for this month
                monthly_rate = loan['monthly_interest_rate']
                interest = balance * monthly_rate
                total_interest += interest

                # Update balance: add interest, subtract payment
                loan['balance'] = balance + interest - payment

                month_data['payments'][str(loan['id'])] = {
                    'payment': round(payment, 2),
                    'interest': round(interest, 2),
                    'balance': round(max(0, loan['balance']), 2)
                }
                month_data['total_payment'] += payment

                # Remove loan if paid off
                if loan['balance'] <= 0.01:  # Account for floating point precision
                    remaining_loans.remove(loan)

            month_data['remaining_balance'] = round(sum(loan['balance'] for loan in remaining_loans), 2)
            schedule.append(month_data)

            if not remaining_loans:
                break

        return {
            'total_debt': round(total_debt, 2),
            'total_interest': round(total_interest, 2),
            'payoff_months': current_month,
            'monthly_payment': round(monthly_payment, 2),
            'schedule': schedule,
            'summary': {
                'method': 'avalanche',
                'loans_paid_off': len(loans) - len(remaining_loans),
                'remaining_loans': len(remaining_loans),
                'total_payments': round(total_debt + total_interest, 2)
            }
        }

    def _calculate_consolidation(self, loans):
        """Calculate Debt Consolidation plan."""
        if not self.consolidation_rate or not self.consolidation_term:
            return self._empty_plan_data()

        total_debt = sum(float(loan.balance) for loan in loans)
        consolidation_rate = float(self.consolidation_rate) / 100 / 12  # Monthly rate
        term_months = self.consolidation_term

        # Calculate consolidated payment using loan amortization formula
        if consolidation_rate == 0:
            monthly_payment = total_debt / term_months
        else:
            monthly_payment = total_debt * (consolidation_rate * (1 + consolidation_rate) ** term_months) / ((1 + consolidation_rate) ** term_months - 1)

        monthly_payment += float(self.extra_payment)

        # Calculate total interest for consolidation
        total_payments = monthly_payment * term_months
        total_interest = total_payments - total_debt

        # Calculate what interest would be without consolidation (more accurate calculation)
        original_interest = 0
        for loan in loans:
            balance = float(loan.balance)
            monthly_rate = float(loan.monthly_interest_rate)
            min_payment = float(loan.minimum_payment)

            # Estimate payoff months for each loan individually using proper amortization
            if monthly_rate == 0:
                estimated_months = balance / min_payment
            else:
                # Use loan amortization formula for each loan
                # PMT = P * (r(1+r)^n) / ((1+r)^n - 1)
                # Solve for n: n = log(PMT / (PMT - P*r)) / log(1+r)
                if min_payment > balance * monthly_rate:
                    estimated_months = - (1 / monthly_rate) * (1 - (balance * monthly_rate) / min_payment)
                else:
                    estimated_months = balance / min_payment

            # Cap at reasonable maximum (30 years)
            estimated_months = min(estimated_months, 360)
            original_interest += balance * monthly_rate * estimated_months

        interest_saved = max(0, original_interest - total_interest)

        schedule = []
        remaining_balance = total_debt

        for month in range(1, term_months + 1):
            interest = remaining_balance * consolidation_rate
            principal = monthly_payment - interest

            if principal > remaining_balance:
                principal = remaining_balance
                monthly_payment = principal + interest

            remaining_balance -= principal

            schedule.append({
                'month': month,
                'payment': round(monthly_payment, 2),
                'principal': round(principal, 2),
                'interest': round(interest, 2),
                'remaining_balance': round(max(0, remaining_balance), 2)
            })

            if remaining_balance <= 0.01:  # Account for floating point precision
                break

        return {
            'total_debt': round(total_debt, 2),
            'total_interest': round(total_interest, 2),
            'payoff_months': term_months,
            'monthly_payment': round(monthly_payment, 2),
            'schedule': schedule,
            'summary': {
                'method': 'consolidation',
                'consolidation_rate': float(self.consolidation_rate),
                'interest_saved': round(interest_saved, 2),
                'loans_consolidated': len(loans),
                'total_payments': round(total_debt + total_interest, 2)
            }
        }


class PlanProgress(models.Model):
    """Track progress on a debt plan."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(DebtPlan, on_delete=models.CASCADE, related_name='progress_entries')
    month = models.PositiveIntegerField(help_text="Month number in the plan")
    actual_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Actual payment made this month"
    )
    notes = models.TextField(blank=True, help_text="Notes about this month's progress")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-month']
        unique_together = ['plan', 'month']
        verbose_name = 'Plan Progress'
        verbose_name_plural = 'Plan Progress'

    def __str__(self):
        return f"{self.plan.name} - Month {self.month}"
