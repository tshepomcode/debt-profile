import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import SubscriptionPlan, UserSubscription, Payment, WaitingList


class SubscriptionPlanTestCase(APITestCase):
    """Test cases for subscription plans."""

    def setUp(self):
        """Set up test data."""
        self.plan = SubscriptionPlan.objects.create(
            name='Test Pro Plan',
            plan_type='pro',
            interval='month',
            price=9.99,
            stripe_price_id='price_test_pro',
            max_loans=50,
            can_export=True,
            can_compare=True,
            is_active=True,
            is_popular=True
        )

    def test_list_subscription_plans(self):
        """Test listing subscription plans."""
        url = reverse('subscriptionplan-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that we get some plans in the response (paginated response)
        self.assertIn('results', response.data)
        self.assertGreater(len(response.data['results']), 0)
        # Verify the test plan is in results
        plan_names = [plan['name'] for plan in response.data['results']]
        self.assertIn('Test Pro Plan', plan_names)


class UserSubscriptionTestCase(APITestCase):
    """Test cases for user subscriptions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.plan = SubscriptionPlan.objects.create(
            name='Test Pro Plan',
            plan_type='pro',
            interval='month',
            price=9.99,
            stripe_price_id='price_test_pro',
            max_loans=50,
            can_export=True,
            can_compare=True,
            is_active=True
        )

    def test_create_subscription_requires_authentication(self):
        """Test that creating subscription requires authentication."""
        url = reverse('usersubscription-create-subscription')
        data = {'plan_id': str(self.plan.id)}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_list_subscriptions(self):
        """Test that authenticated users can list their subscriptions."""
        self.client.force_authenticate(user=self.user)
        url = reverse('usersubscription-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PaymentTestCase(APITestCase):
    """Test cases for payments."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_list_payments_requires_authentication(self):
        """Test that listing payments requires authentication."""
        url = reverse('payment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_list_payments(self):
        """Test that authenticated users can list their payments."""
        self.client.force_authenticate(user=self.user)
        url = reverse('payment-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WaitingListTestCase(APITestCase):
    """Test cases for waiting list."""

    def test_join_waiting_list(self):
        """Test joining the waiting list."""
        url = reverse('waitinglist-join')
        data = {
            'email': 'test@example.com',
            'name': 'Test User',
            'interest': 'pro'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WaitingList.objects.count(), 1)

    def test_duplicate_email_waiting_list(self):
        """Test that duplicate emails are rejected."""
        # First signup
        WaitingList.objects.create(
            email='test@example.com',
            name='Test User',
            interest='pro'
        )

        # Try to signup again
        url = reverse('waitinglist-join')
        data = {
            'email': 'test@example.com',
            'name': 'Test User 2',
            'interest': 'premium'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(WaitingList.objects.count(), 1)


class BillingSummaryTestCase(APITestCase):
    """Test cases for billing summary."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_billing_summary_requires_authentication(self):
        """Test that billing summary requires authentication."""
        url = reverse('waitinglist-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_get_summary(self):
        """Test that authenticated users can get billing summary."""
        self.client.force_authenticate(user=self.user)
        url = reverse('waitinglist-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('current_plan', response.data)
        self.assertIn('total_payments', response.data)


class ModelTestCase(TestCase):
    """Test cases for model methods."""

    def test_subscription_plan_str(self):
        """Test SubscriptionPlan string representation."""
        plan = SubscriptionPlan.objects.create(
            name='Test Plan',
            plan_type='pro',
            interval='month',
            price=9.99,
            stripe_price_id='price_test',
            max_loans=50,
            is_active=True
        )
        self.assertEqual(str(plan), 'Test Plan - $9.99/month')

    def test_user_subscription_str(self):
        """Test UserSubscription string representation."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        plan = SubscriptionPlan.objects.create(
            name='Test Plan',
            plan_type='pro',
            interval='month',
            price=9.99,
            stripe_price_id='price_test',
            max_loans=50,
            is_active=True
        )
        subscription = UserSubscription.objects.create(
            user=user,
            plan=plan,
            status='active'
        )
        expected = f'testuser - Test Plan (active)'
        self.assertEqual(str(subscription), expected)

    def test_payment_str(self):
        """Test Payment string representation."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        payment = Payment.objects.create(
            user=user,
            payment_type='subscription',
            amount=9.99,
            currency='usd',
            status='succeeded'
        )
        expected = 'testuser - $9.99 (succeeded)'
        self.assertEqual(str(payment), expected)

    def test_waiting_list_str(self):
        """Test WaitingList string representation."""
        waiting_list = WaitingList.objects.create(
            email='test@example.com',
            name='Test User',
            interest='pro'
        )
        expected = 'Test User (test@example.com)'
        self.assertEqual(str(waiting_list), expected)
