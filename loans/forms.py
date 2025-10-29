from django import forms
from .models import Loan


class LoanForm(forms.ModelForm):
    """Form for creating and editing loans."""

    class Meta:
        model = Loan
        fields = ['name', 'balance', 'interest_rate', 'minimum_payment', 'creditor', 'loan_type']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., Student Loan, Credit Card'
            }),
            'balance': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Current balance'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': 'Annual interest rate (%)'
            }),
            'minimum_payment': forms.NumberInput(attrs={
                'class': 'input input-bordered w-full',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Monthly minimum payment'
            }),
            'creditor': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Bank or lender name'
            }),
            'loan_type': forms.Select(attrs={
                'class': 'select select-bordered w-full'
            }),
        }

    def clean_balance(self):
        balance = self.cleaned_data.get('balance')
        if balance <= 0:
            raise forms.ValidationError('Balance must be greater than zero.')
        return balance

    def clean_interest_rate(self):
        rate = self.cleaned_data.get('interest_rate')
        if rate < 0:
            raise forms.ValidationError('Interest rate cannot be negative.')
        return rate

    def clean_minimum_payment(self):
        payment = self.cleaned_data.get('minimum_payment')
        if payment <= 0:
            raise forms.ValidationError('Minimum payment must be greater than zero.')
        return payment


class BulkLoanForm(forms.Form):
    """Form for bulk loan creation."""

    loans_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full',
            'rows': 10,
            'placeholder': 'Paste loan data in CSV format:\nName,Balance,Interest Rate,Min Payment,Creditor,Type\nStudent Loan,15000,5.5,200,Bank A,Student\nCredit Card,2500,18.99,75,Bank B,Credit Card'
        }),
        help_text='Paste loan data in CSV format with headers: Name,Balance,Interest Rate,Min Payment,Creditor,Type'
    )

    def clean_loans_data(self):
        data = self.cleaned_data.get('loans_data')
        lines = data.strip().split('\n')

        if len(lines) < 2:
            raise forms.ValidationError('Please provide at least a header row and one data row.')

        # Parse CSV data
        parsed_loans = []
        for i, line in enumerate(lines[1:], 2):  # Skip header, start from line 2
            parts = [part.strip() for part in line.split(',')]
            if len(parts) != 6:
                raise forms.ValidationError(f'Line {i}: Expected 6 columns, got {len(parts)}.')

            try:
                loan_data = {
                    'name': parts[0],
                    'balance': float(parts[1]),
                    'interest_rate': float(parts[2]),
                    'minimum_payment': float(parts[3]),
                    'creditor': parts[4],
                    'loan_type': parts[5],
                }

                # Validate data
                if loan_data['balance'] <= 0:
                    raise forms.ValidationError(f'Line {i}: Balance must be greater than zero.')
                if loan_data['interest_rate'] < 0:
                    raise forms.ValidationError(f'Line {i}: Interest rate cannot be negative.')
                if loan_data['minimum_payment'] <= 0:
                    raise forms.ValidationError(f'Line {i}: Minimum payment must be greater than zero.')

                parsed_loans.append(loan_data)

            except ValueError as e:
                raise forms.ValidationError(f'Line {i}: Invalid number format - {str(e)}')

        return parsed_loans