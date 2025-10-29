from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from django.shortcuts import render
from .views import DebtPlanViewSet, PlanProgressViewSet

router = DefaultRouter()
router.register(r'plans', DebtPlanViewSet, basename='debtplan')

# Nested router for plan progress
plans_router = routers.NestedDefaultRouter(router, r'plans', lookup='plan')
plans_router.register(r'progress', PlanProgressViewSet, basename='plan-progress')

def plan_compare_view(request):
    """Web view for comparing debt plans."""
    if request.method == 'POST':
        plan_ids = request.POST.getlist('plan_ids')
        if len(plan_ids) >= 2:
            # Import here to avoid circular imports
            from .models import DebtPlan
            plans = DebtPlan.objects.filter(id__in=plan_ids, user=request.user)
            if plans.count() == len(plan_ids):
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

                context = {
                    'comparison_data': comparison_data,
                    'best_interest_savings': max(comparison_data, key=lambda x: x['total_interest_saved']),
                    'fastest_payoff': min(comparison_data, key=lambda x: x['payoff_months']),
                    'lowest_payment': min(comparison_data, key=lambda x: x['monthly_payment'])
                }
                return render(request, 'plans/plan_compare.html', context)

    # If GET or invalid POST, redirect to plans list
    from django.shortcuts import redirect
    return redirect('plans:list')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(plans_router.urls)),

    # Web URLs
    path('compare/', plan_compare_view, name='compare'),
]