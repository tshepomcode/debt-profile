from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Avg, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from billing.permissions import HasLoanLimit
from .models import Loan
from .serializers import LoanSerializer, LoanSummarySerializer
from .forms import LoanForm


class LoanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user loans."""

    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated, HasLoanLimit]

    def get_queryset(self):
        """Return loans for the authenticated user."""
        return Loan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a loan for the authenticated user."""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics for user's loans."""
        loans = self.get_queryset().filter(is_active=True)

        if not loans.exists():
            return Response({
                'total_loans': 0,
                'total_balance': 0,
                'total_minimum_payments': 0,
                'average_interest_rate': 0
            })

        summary_data = loans.aggregate(
            total_loans=Count('id'),
            total_balance=Sum('balance'),
            total_minimum_payments=Sum('minimum_payment'),
            average_interest_rate=Avg('interest_rate')
        )

        serializer = LoanSummarySerializer(summary_data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle the active status of a loan."""
        loan = self.get_object()

        if loan.user != request.user:
            return Response(
                {'error': 'You can only modify your own loans.'},
                status=status.HTTP_403_FORBIDDEN
            )

        loan.is_active = not loan.is_active
        loan.save()

        serializer = self.get_serializer(loan)
        return Response(serializer.data)

    @action(detail=False, methods=['delete'])
    def delete_inactive(self, request):
        """Delete all inactive loans for the user."""
        deleted_count, _ = self.get_queryset().filter(is_active=False).delete()

        return Response({
            'message': f'Successfully deleted {deleted_count} inactive loans.'
        })


# Web Views
@login_required
def dashboard(request):
    """Main dashboard view showing user's debt overview."""
    loans = Loan.objects.filter(user=request.user, is_active=True)
    total_balance = loans.aggregate(Sum('balance'))['balance__sum'] or 0
    total_payments = loans.aggregate(Sum('minimum_payment'))['minimum_payment__sum'] or 0
    avg_rate = loans.aggregate(Avg('interest_rate'))['interest_rate__avg'] or 0

    context = {
        'loans': loans,
        'total_balance': total_balance,
        'total_payments': total_payments,
        'avg_rate': avg_rate,
        'loan_count': loans.count(),
    }
    return render(request, 'loans/dashboard.html', context)


@login_required
def loan_list(request):
    """List all user's loans."""
    loans = Loan.objects.filter(user=request.user)
    return render(request, 'loans/loan_list.html', {'loans': loans})


@login_required
def loan_create(request):
    """Create a new loan."""
    if request.method == 'POST':
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            loan.user = request.user
            loan.save()
            messages.success(request, 'Loan added successfully!')
            return redirect('loans:list')
    else:
        form = LoanForm()

    return render(request, 'loans/loan_form.html', {'form': form, 'title': 'Add New Loan'})


@login_required
def loan_detail(request, pk):
    """View loan details."""
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    return render(request, 'loans/loan_detail.html', {'loan': loan})


@login_required
@require_POST
def loan_toggle_active(request, pk):
    """Toggle loan active status via HTMX."""
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    loan.is_active = not loan.is_active
    loan.save()

    return JsonResponse({
        'success': True,
        'is_active': loan.is_active,
        'message': f'Loan {"activated" if loan.is_active else "deactivated"} successfully!'
    })


@login_required
@require_POST
def loan_delete(request, pk):
    """Delete a loan via HTMX."""
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    loan.delete()

    return JsonResponse({
        'success': True,
        'message': 'Loan deleted successfully!'
    })
