from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from .models import Loan


class LoanModelTest(TestCase):
    """Test cases for Loan model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_loan_creation(self):
        """Test loan creation with valid data."""
        loan = Loan.objects.create(
            user=self.user,
            name='Test Loan',
            balance=Decimal('10000.00'),
            interest_rate=Decimal('5.5'),
            minimum_payment=Decimal('200.00')
        )

        self.assertEqual(loan.name, 'Test Loan')
        self.assertEqual(loan.balance, Decimal('10000.00'))
        self.assertEqual(loan.interest_rate, Decimal('5.5'))
        self.assertEqual(loan.minimum_payment, Decimal('200.00'))
        self.assertEqual(loan.user, self.user)

    def test_monthly_interest_rate_calculation(self):
        """Test monthly interest rate calculation."""
        loan = Loan.objects.create(
            user=self.user,
            name='Test Loan',
            balance=Decimal('10000.00'),
            interest_rate=Decimal('12.0'),  # 12% APR
            minimum_payment=Decimal('200.00')
        )

        expected_monthly_rate = Decimal('12.0') / Decimal('100') / Decimal('12')  # 0.01
        self.assertEqual(loan.monthly_interest_rate, expected_monthly_rate)

    def test_estimated_payoff_months_calculation(self):
        """Test estimated payoff months calculation."""
        loan = Loan.objects.create(
            user=self.user,
            name='Test Loan',
            balance=Decimal('10000.00'),
            interest_rate=Decimal('0.0'),  # 0% interest for simple calculation
            minimum_payment=Decimal('500.00')
        )

        # With $500 payment on $10,000 balance, should take 20 months
        self.assertEqual(loan.estimated_payoff_months, 20)


class LoanAPITest(APITestCase):
    """Test cases for Loan API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Clean up any existing loans for this user
        Loan.objects.filter(user=self.user).delete()

        # Create test loan
        self.loan = Loan.objects.create(
            user=self.user,
            name='Test Loan',
            balance=Decimal('10000.00'),
            interest_rate=Decimal('5.5'),
            minimum_payment=Decimal('200.00')
        )

    def test_list_loans(self):
        """Test listing user's loans."""
        response = self.client.get('/api/loans/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The queryset should already filter by user, so we should only get 1 loan
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Loan')

    def test_create_loan(self):
        """Test creating a new loan."""
        data = {
            'name': 'New Loan',
            'balance': '15000.00',
            'interest_rate': '7.5',
            'minimum_payment': '300.00'
        }
        response = self.client.post('/api/loans/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Loan')
        self.assertEqual(Loan.objects.count(), 2)

    def test_create_loan_validation(self):
        """Test loan creation validation."""
        # Test negative balance
        data = {
            'name': 'Invalid Loan',
            'balance': '-1000.00',
            'interest_rate': '5.0',
            'minimum_payment': '50.00'
        }
        response = self.client.post('/api/loans/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_loan(self):
        """Test retrieving a specific loan."""
        response = self.client.get(f'/api/loans/{self.loan.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Loan')

    def test_update_loan(self):
        """Test updating a loan."""
        data = {
            'name': 'Updated Loan',
            'balance': '12000.00',
            'interest_rate': '6.0',
            'minimum_payment': '250.00'
        }
        response = self.client.put(f'/api/loans/{self.loan.id}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.name, 'Updated Loan')

    def test_delete_loan(self):
        """Test deleting a loan."""
        response = self.client.delete(f'/api/loans/{self.loan.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Loan.objects.count(), 0)

    def test_loan_summary(self):
        """Test loan summary endpoint."""
        # Create another loan
        Loan.objects.create(
            user=self.user,
            name='Second Loan',
            balance=Decimal('5000.00'),
            interest_rate=Decimal('4.0'),
            minimum_payment=Decimal('100.00')
        )

        response = self.client.get('/api/loans/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_loans'], 2)
        self.assertEqual(response.data['total_balance'], '15000.00')

    def test_toggle_active(self):
        """Test toggling loan active status."""
        # Initially active
        self.assertTrue(self.loan.is_active)

        response = self.client.post(f'/api/loans/{self.loan.id}/toggle_active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.loan.refresh_from_db()
        self.assertFalse(self.loan.is_active)

        # Toggle back
        response = self.client.post(f'/api/loans/{self.loan.id}/toggle_active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.loan.refresh_from_db()
        self.assertTrue(self.loan.is_active)

    def test_unauthorized_access(self):
        """Test that users can't access other users' loans."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )

        # Try to access loan from different user
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'/api/loans/{self.loan.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
