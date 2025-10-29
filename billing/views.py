import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Sum
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.shortcuts import render
from django.core.paginator import Paginator
from .models import SubscriptionPlan, UserSubscription, Payment, WaitingList
from .serializers import (
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    PaymentSerializer, WaitingListSerializer, BillingSummarySerializer
)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing subscription plans."""

    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]  # Allow anyone to view plans


class UserSubscriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user subscriptions."""

    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return subscriptions for the authenticated user."""
        return UserSubscription.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a subscription for the authenticated user."""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def create_subscription(self, request):
        """Create a new subscription with Stripe."""
        plan_id = request.data.get('plan_id')
        payment_method_id = request.data.get('payment_method_id')

        if not plan_id:
            return Response({'error': 'Plan ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Invalid plan'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already has an active subscription
        existing_subscription = UserSubscription.objects.filter(
            user=request.user, status__in=['active', 'trialing']
        ).first()

        if existing_subscription:
            return Response({'error': 'User already has an active subscription'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Create or retrieve Stripe customer
            customer = self._get_or_create_stripe_customer(request.user)

            # Create subscription data
            subscription_data = {
                'customer': customer.id,
                'items': [{
                    'price': plan.stripe_price_id,
                }],
                'payment_behavior': 'default_incomplete',
                'expand': ['latest_invoice.payment_intent'],
            }

            if payment_method_id:
                subscription_data['default_payment_method'] = payment_method_id

            # Create trial if plan supports it
            if plan.plan_type == 'pro':
                subscription_data['trial_period_days'] = 14

            # Create Stripe subscription
            stripe_subscription = stripe.Subscription.create(**subscription_data)

            # Create local subscription record
            user_subscription = UserSubscription.objects.create(
                user=request.user,
                plan=plan,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=customer.id,
                stripe_price_id=plan.stripe_price_id,
                status=stripe_subscription.status,
                current_period_start=timezone.datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=timezone.datetime.fromtimestamp(stripe_subscription.current_period_end),
                trial_start=timezone.datetime.fromtimestamp(stripe_subscription.trial_start) if stripe_subscription.trial_start else None,
                trial_end=timezone.datetime.fromtimestamp(stripe_subscription.trial_end) if stripe_subscription.trial_end else None,
            )

            # Create payment record for the invoice
            if stripe_subscription.latest_invoice:
                invoice = stripe_subscription.latest_invoice
                Payment.objects.create(
                    user=request.user,
                    subscription=user_subscription,
                    payment_type='subscription',
                    amount=invoice.amount_due / 100,  # Convert from cents
                    currency=invoice.currency,
                    stripe_payment_intent_id=invoice.payment_intent.id if invoice.payment_intent else None,
                    status='pending',
                    description=f'Subscription to {plan.name}',
                )

            serializer = self.get_serializer(user_subscription)
            return Response({
                'subscription': serializer.data,
                'client_secret': stripe_subscription.latest_invoice.payment_intent.client_secret if stripe_subscription.latest_invoice and stripe_subscription.latest_invoice.payment_intent else None
            }, status=status.HTTP_201_CREATED)

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Failed to create subscription'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def cancel_subscription(self, request, pk=None):
        """Cancel a user's subscription."""
        subscription = self.get_object()

        if subscription.user != request.user:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Cancel at period end by default
            cancel_at_period_end = request.data.get('cancel_at_period_end', True)

            if cancel_at_period_end:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                subscription.cancel_at_period_end = True
                subscription.save()
                message = 'Subscription will be canceled at the end of the current period'
            else:
                # Cancel immediately
                stripe_subscription = stripe.Subscription.delete(subscription.stripe_subscription_id)
                subscription.status = stripe_subscription.status
                subscription.save()
                message = 'Subscription canceled immediately'

            serializer = self.get_serializer(subscription)
            return Response({
                'message': message,
                'subscription': serializer.data
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_or_create_stripe_customer(self, user):
        """Get or create Stripe customer for user."""
        if hasattr(user, 'subscription') and user.subscription.stripe_customer_id:
            try:
                return stripe.Customer.retrieve(user.subscription.stripe_customer_id)
            except stripe.error.StripeError:
                pass

        # Create new customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.get_full_name() or user.username,
            metadata={'user_id': str(user.id)}
        )

        # Update local record if exists
        if hasattr(user, 'subscription'):
            user.subscription.stripe_customer_id = customer.id
            user.subscription.save()

        return customer


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing payments."""

    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return payments for the authenticated user."""
        return Payment.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a payment for the authenticated user."""
        serializer.save(user=self.request.user)


class WaitingListViewSet(viewsets.ModelViewSet):
    """ViewSet for managing waiting list."""

    serializer_class = WaitingListSerializer
    permission_classes = [AllowAny]  # Allow anyone to join waiting list

    def get_queryset(self):
        """Return waiting list entries (admin only)."""
        if self.request.user.is_staff:
            return WaitingList.objects.all()
        return WaitingList.objects.none()

    @action(detail=False, methods=['post'])
    def join(self, request):
        """Join the waiting list."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Successfully joined the waiting list!',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def notify_users(self, request):
        """Send notification emails to waiting list users (admin only)."""
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        subject = request.data.get('subject', 'Debt Profile is now available!')
        message = request.data.get('message', 'Great news! Debt Profile is now live. Sign up today!')
        interest_filter = request.data.get('interest_filter')  # Optional filter by interest level

        # Get waiting list users
        queryset = WaitingList.objects.filter(is_notified=False)
        if interest_filter:
            queryset = queryset.filter(interest=interest_filter)

        users_to_notify = list(queryset)
        notified_count = 0

        for waiting_user in users_to_notify:
            try:
                # Send email notification
                email_context = {
                    'name': waiting_user.name,
                    'email': waiting_user.email,
                    'subject': subject,
                    'message': message,
                    'site': Site.objects.get_current(),
                }

                html_message = render_to_string('billing/waiting_list_notification.html', email_context)
                plain_message = f"Hi {waiting_user.name},\n\n{message}\n\nVisit us at {Site.objects.get_current().domain}"

                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[waiting_user.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                # Mark as notified
                waiting_user.is_notified = True
                waiting_user.save()
                notified_count += 1

            except Exception as e:
                print(f"Failed to send email to {waiting_user.email}: {e}")
                continue

        return Response({
            'message': f'Successfully notified {notified_count} users',
            'notified_count': notified_count
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def summary(self, request):
        """Get billing summary for the authenticated user."""
        user = request.user

        # Get current subscription
        current_subscription = UserSubscription.objects.filter(
            user=user, status='active'
        ).first()

        # Get payment summary
        payments = Payment.objects.filter(user=user)
        total_payments = payments.aggregate(
            total=Sum('amount')
        )['total'] or 0

        # Get waiting list count (for admin)
        waiting_list_count = WaitingList.objects.count() if user.is_staff else 0

        summary_data = {
            'current_plan': current_subscription.plan.name if current_subscription else 'Free',
            'subscription_status': current_subscription.status if current_subscription else 'None',
            'next_billing_date': current_subscription.current_period_end if current_subscription else None,
            'total_payments': total_payments,
            'waiting_list_count': waiting_list_count
        }

        serializer = BillingSummarySerializer(summary_data)
        return Response(serializer.data)


# Web views for waiting list management
def waiting_list_management(request):
    """Web view for managing waiting list (admin only)."""
    if not request.user.is_staff:
        from django.shortcuts import redirect
        return redirect('dashboard')

    # Get statistics
    total_signups = WaitingList.objects.count()
    notified_count = WaitingList.objects.filter(is_notified=True).count()
    not_notified_count = WaitingList.objects.filter(is_notified=False).count()

    # This week's signups
    from django.utils import timezone
    week_ago = timezone.now() - timezone.timedelta(days=7)
    this_week_signups = WaitingList.objects.filter(created_at__gte=week_ago).count()

    # Handle notification sending
    if request.method == 'POST' and 'subject' in request.POST:
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        interest_filter = request.POST.get('interest_filter')

        # Get waiting list users
        queryset = WaitingList.objects.filter(is_notified=False)
        if interest_filter:
            queryset = queryset.filter(interest=interest_filter)

        users_to_notify = list(queryset)
        notified_count = 0

        for waiting_user in users_to_notify:
            try:
                # Send email notification
                email_context = {
                    'name': waiting_user.name,
                    'email': waiting_user.email,
                    'subject': subject,
                    'message': message,
                    'site': Site.objects.get_current(),
                }

                html_message = render_to_string('billing/waiting_list_notification.html', email_context)
                plain_message = f"Hi {waiting_user.name},\n\n{message}\n\nVisit us at {Site.objects.get_current().domain}"

                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[waiting_user.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                # Mark as notified
                waiting_user.is_notified = True
                waiting_user.save()
                notified_count += 1

            except Exception as e:
                print(f"Failed to send email to {waiting_user.email}: {e}")
                continue

        # Update statistics after sending
        total_signups = WaitingList.objects.count()
        notified_count = WaitingList.objects.filter(is_notified=True).count()
        not_notified_count = WaitingList.objects.filter(is_notified=False).count()

    # Get paginated waiting list
    waiting_list = WaitingList.objects.all().order_by('-created_at')
    paginator = Paginator(waiting_list, 50)  # 50 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'waiting_list': page_obj,
        'total_signups': total_signups,
        'notified_count': notified_count,
        'not_notified_count': not_notified_count,
        'this_week_signups': this_week_signups,
    }

    return render(request, 'billing/waiting_list_management.html', context)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the event
    if event.type == 'invoice.payment_succeeded':
        handle_payment_succeeded(event.data.object)
    elif event.type == 'invoice.payment_failed':
        handle_payment_failed(event.data.object)
    elif event.type == 'customer.subscription.updated':
        handle_subscription_updated(event.data.object)
    elif event.type == 'customer.subscription.deleted':
        handle_subscription_deleted(event.data.object)
    elif event.type == 'checkout.session.completed':
        handle_checkout_completed(event.data.object)
    else:
        # Unexpected event type
        print(f'Unhandled event type {event.type}')

    return HttpResponse(status=200)


def handle_payment_succeeded(invoice):
    """Handle successful payment."""
    subscription_id = invoice.subscription
    if not subscription_id:
        return

    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=subscription_id)
        payment = Payment.objects.filter(
            stripe_payment_intent_id=invoice.payment_intent
        ).first()

        if payment:
            payment.status = 'succeeded'
            payment.paid_at = timezone.now()
            payment.save()

        # Update subscription status if needed
        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        user_subscription.status = stripe_subscription.status
        user_subscription.current_period_start = timezone.datetime.fromtimestamp(stripe_subscription.current_period_start)
        user_subscription.current_period_end = timezone.datetime.fromtimestamp(stripe_subscription.current_period_end)
        user_subscription.save()

    except UserSubscription.DoesNotExist:
        print(f'Subscription {subscription_id} not found')
    except Exception as e:
        print(f'Error handling payment succeeded: {e}')


def handle_payment_failed(invoice):
    """Handle failed payment."""
    subscription_id = invoice.subscription
    if not subscription_id:
        return

    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=subscription_id)
        payment = Payment.objects.filter(
            stripe_payment_intent_id=invoice.payment_intent
        ).first()

        if payment:
            payment.status = 'failed'
            payment.failure_reason = 'Payment failed'
            payment.save()

        # Update subscription status
        user_subscription.status = 'past_due'
        user_subscription.save()

    except UserSubscription.DoesNotExist:
        print(f'Subscription {subscription_id} not found')
    except Exception as e:
        print(f'Error handling payment failed: {e}')


def handle_subscription_updated(stripe_subscription):
    """Handle subscription updates."""
    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=stripe_subscription.id)
        user_subscription.status = stripe_subscription.status
        user_subscription.current_period_start = timezone.datetime.fromtimestamp(stripe_subscription.current_period_start)
        user_subscription.current_period_end = timezone.datetime.fromtimestamp(stripe_subscription.current_period_end)
        user_subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end
        user_subscription.save()

    except UserSubscription.DoesNotExist:
        print(f'Subscription {stripe_subscription.id} not found')
    except Exception as e:
        print(f'Error handling subscription updated: {e}')


def handle_subscription_deleted(stripe_subscription):
    """Handle subscription cancellation."""
    try:
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=stripe_subscription.id)
        user_subscription.status = 'canceled'
        user_subscription.save()

    except UserSubscription.DoesNotExist:
        print(f'Subscription {stripe_subscription.id} not found')
    except Exception as e:
        print(f'Error handling subscription deleted: {e}')


def handle_checkout_completed(session):
    """Handle completed checkout session."""
    # Handle one-time purchases or other checkout completions
    print(f'Checkout completed: {session.id}')
