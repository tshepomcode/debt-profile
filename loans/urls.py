from django.shortcuts import redirect
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from .views import (
    LoanViewSet, dashboard, loan_list, loan_create, loan_detail,
    loan_toggle_active, loan_delete
)

router = DefaultRouter()
router.register(r'', LoanViewSet, basename='loan')

urlpatterns = [
    # API routes
    path('api/', include(router.urls)),

    # Web routes
    path('', dashboard, name='dashboard'),
    path('loans/', loan_list, name='list'),
    path('loans/create/', loan_create, name='create'),
    path('loans/<uuid:pk>/', loan_detail, name='detail'),
    path('loans/<uuid:pk>/toggle/', loan_toggle_active, name='toggle'),
    path('loans/<uuid:pk>/delete/', loan_delete, name='delete'),

    # Profile redirect
    path('accounts/profile/', lambda request: redirect('loans:dashboard'), name='profile_redirect'),
]