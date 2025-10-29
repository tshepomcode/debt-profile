from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet, UserSubscriptionViewSet, PaymentViewSet,
    WaitingListViewSet, stripe_webhook, waiting_list_management
)

app_name = 'billing'

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='subscriptionplan')
router.register(r'subscriptions', UserSubscriptionViewSet, basename='usersubscription')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'waiting-list', WaitingListViewSet, basename='waitinglist')

urlpatterns = [
    path('', include(router.urls)),
    path('webhooks/stripe/', stripe_webhook, name='stripe-webhook'),

    # Web URLs
    path('waiting-list/manage/', waiting_list_management, name='waiting-list-management'),
]