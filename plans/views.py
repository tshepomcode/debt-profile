from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Count, Sum
from django.http import JsonResponse
from billing.permissions import HasPlanLimit, CanExportPlans, CanComparePlans
from .models import DebtPlan, PlanProgress
from .serializers import (
    DebtPlanSerializer, DebtPlanCalculateSerializer,
    PlanProgressSerializer, DebtPlanSummarySerializer
)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from django.http import HttpResponse
from io import BytesIO
import json

# Import Loan model for plan creation view
from loans.models import Loan


class DebtPlanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing debt plans."""

    serializer_class = DebtPlanSerializer
    permission_classes = [IsAuthenticated, HasPlanLimit]

    def get_queryset(self):
        """Return debt plans for the authenticated user."""
        return DebtPlan.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a debt plan for the authenticated user."""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """Calculate debt reduction plan."""
        plan = self.get_object()

        if plan.user != request.user:
            return Response(
                {'error': 'You can only calculate your own plans.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Calculate the plan
        plan_data = plan.calculate_plan()

        # Update plan with calculated data
        plan.total_debt = plan_data['total_debt']
        plan.total_interest_saved = plan_data.get('total_interest', 0)
        plan.payoff_months = plan_data['payoff_months']
        plan.total_payments = plan_data.get('monthly_payment', 0) * plan_data['payoff_months']
        plan.plan_data = plan_data
        plan.status = 'active'
        plan.save()

        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a debt plan (set as user's active plan)."""
        plan = self.get_object()

        if plan.user != request.user:
            return Response(
                {'error': 'You can only activate your own plans.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Ensure plan is calculated before activation
        if not plan.plan_data:
            return Response(
                {'error': 'Plan must be calculated before activation.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        plan.is_active = True
        plan.status = 'active'
        plan.save()

        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark a debt plan as completed."""
        plan = self.get_object()

        if plan.user != request.user:
            return Response(
                {'error': 'You can only complete your own plans.'},
                status=status.HTTP_403_FORBIDDEN
            )

        plan.status = 'completed'
        plan.is_active = False
        plan.save()

        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, CanExportPlans])
    def export(self, request, pk=None):
        """Export debt plan data as PDF (premium feature)."""
        plan = self.get_object()

        if plan.user != request.user:
            return Response(
                {'error': 'You can only export your own plans.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create PDF response
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1  # Center alignment
        )
        story.append(Paragraph(f"{plan.name} - Debt Reduction Plan", title_style))
        story.append(Spacer(1, 12))

        # Plan Overview
        story.append(Paragraph("Plan Overview", styles['Heading2']))
        story.append(Spacer(1, 12))

        overview_data = [
            ['Method', plan.get_method_display()],
            ['Total Debt', f"${plan.total_debt:,.0f}"],
            ['Monthly Payment', f"${plan.total_payments/plan.payoff_months:,.0f}"],
            ['Payoff Time', f"{plan.payoff_months} months"],
            ['Interest Saved', f"${plan.total_interest_saved:,.0f}"],
            ['Total Payments', f"${plan.total_payments:,.0f}"]
        ]

        overview_table = Table(overview_data, colWidths=[200, 200])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 24))

        # Included Loans
        story.append(Paragraph("Included Loans", styles['Heading2']))
        story.append(Spacer(1, 12))

        loans_data = [['Name', 'Balance', 'Interest Rate', 'Min Payment']]
        for loan in plan.loans.all():
            loans_data.append([
                loan.name,
                f"${loan.balance:,.0f}",
                f"{loan.interest_rate}%",
                f"${loan.minimum_payment:,.0f}"
            ])

        loans_table = Table(loans_data, colWidths=[150, 100, 100, 100])
        loans_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9)
        ]))
        story.append(loans_table)
        story.append(Spacer(1, 24))

        # Payment Schedule (first 24 months)
        if plan.plan_data and 'schedule' in plan.plan_data:
            story.append(Paragraph("Payment Schedule (First 24 Months)", styles['Heading2']))
            story.append(Spacer(1, 12))

            schedule_data = [['Month', 'Payment', 'Principal', 'Interest', 'Balance']]
            for month_data in plan.plan_data['schedule'][:24]:
                schedule_data.append([
                    str(month_data['month']),
                    f"${month_data['total_payment']:,.0f}",
                    f"${month_data['payments'][list(month_data['payments'].keys())[0]]['payment']:,.0f}",
                    f"${month_data['payments'][list(month_data['payments'].keys())[0]]['interest']:,.0f}",
                    f"${month_data['remaining_balance']:,.0f}"
                ])

            schedule_table = Table(schedule_data, colWidths=[60, 80, 80, 80, 100])
            schedule_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 7)
            ]))
            story.append(schedule_table)

        # Disclaimer
        story.append(Spacer(1, 24))
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.red
        )
        story.append(Paragraph("Disclaimer: This is a financial planning tool for educational purposes. " +
                             "Please consult with a qualified financial advisor before making financial decisions.", disclaimer_style))

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        # Return PDF response
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{plan.name.replace(" ", "_")}_plan.pdf"'
        return response

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanComparePlans])
    def compare(self, request):
        """Compare multiple debt plans (premium feature)."""
        plan_ids = request.data.get('plan_ids', [])

        if not plan_ids or len(plan_ids) < 2:
            return Response(
                {'error': 'At least 2 plan IDs are required for comparison.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(plan_ids) > 4:  # Limit comparison to 4 plans
            return Response(
                {'error': 'Cannot compare more than 4 plans at once.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        plans = DebtPlan.objects.filter(
            id__in=plan_ids,
            user=request.user
        )

        if plans.count() != len(plan_ids):
            return Response(
                {'error': 'One or more plans not found or not owned by you.'},
                status=status.HTTP_404_NOT_FOUND
            )

        comparison_data = []
        for plan in plans:
            comparison_data.append({
                'id': plan.id,
                'name': plan.name,
                'method': plan.get_method_display(),
                'total_debt': plan.total_debt,
                'total_interest_saved': plan.total_interest_saved,
                'payoff_months': plan.payoff_months,
                'monthly_payment': plan.total_payments / plan.payoff_months if plan.payoff_months else 0,
                'total_payments': plan.total_payments
            })

        return Response({
            'comparison_data': comparison_data,
            'best_interest_savings': max(comparison_data, key=lambda x: x['total_interest_saved']),
            'fastest_payoff': min(comparison_data, key=lambda x: x['payoff_months']),
            'lowest_payment': min(comparison_data, key=lambda x: x['monthly_payment'])
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics for user's debt plans."""
        plans = self.get_queryset()

        summary_data = plans.aggregate(
            total_plans=Count('id'),
            active_plans=Count('id', filter=models.Q(status='active')),
            completed_plans=Count('id', filter=models.Q(status='completed')),
            total_debt_managed=Sum('total_debt'),
            total_interest_saved=Sum('total_interest_saved')
        )

        # Handle None values
        summary_data['total_debt_managed'] = summary_data['total_debt_managed'] or 0
        summary_data['total_interest_saved'] = summary_data['total_interest_saved'] or 0

        serializer = DebtPlanSummarySerializer(summary_data)
        return Response(serializer.data)


class PlanProgressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing plan progress entries."""

    serializer_class = PlanProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return progress entries for user's plans."""
        return PlanProgress.objects.filter(plan__user=self.request.user)

    def perform_create(self, serializer):
        """Create progress entry and ensure it belongs to user's plan."""
        plan = serializer.validated_data['plan']
        if plan.user != self.request.user:
            raise serializers.ValidationError("You can only add progress to your own plans.")
        serializer.save()

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent progress entries."""
        recent_progress = self.get_queryset().order_by('-created_at')[:10]
        serializer = self.get_serializer(recent_progress, many=True)
        return Response(serializer.data)


# Web Views
@login_required
def plan_create(request):
    """Create a new debt plan."""
    # Get user's active loans
    active_loans = Loan.objects.filter(user=request.user, is_active=True)
    total_debt = active_loans.aggregate(Sum('balance'))['balance__sum'] or 0
    
    context = {
        'active_loans': active_loans,
        'total_debt': total_debt,
        'loan_count': active_loans.count(),
    }
    return render(request, 'plans/plan_form.html', context)


@login_required
def plan_list(request):
    """List all user's debt plans."""
    plans = DebtPlan.objects.filter(user=request.user)
    total_debt = plans.aggregate(Sum('total_debt'))['total_debt__sum'] or 0
    total_saved = plans.aggregate(Sum('total_interest_saved'))['total_interest_saved__sum'] or 0
    active_plans = plans.filter(status='active')
    
    context = {
        'plans': plans,
        'total_debt': total_debt,
        'total_saved': total_saved,
        'active_plans': active_plans,
    }
    return render(request, 'plans/plan_list.html', context)
