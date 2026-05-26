from django.db import models
from decimal import Decimal
from .models import (
    Order,
    CompensationPlan,
    SCRateTable,
    SCFlatRateTable,
    Employee,
    Sale,
    Commission,
)


def calculate_commission_for_order(order):
    """
    Calculate commission for one order and save a Commission record.
    
    Lookup priority:
    1. Try to find compensation plan by position_name (if provided)
    2. Fall back to compensation plan by role (if position not found)
    """

    plan = None
    
    # Step 1: Try to find compensation plan by position_name
    if order.position_name:
        plan = CompensationPlan.objects.filter(
            position_name=order.position_name,
            status='Active'
        ).first()
    
    # Step 2: If not found by position, try to find by role (from UserProfile)
    if not plan and order.employee_id:
        from .models import UserProfile
        user_profile = UserProfile.objects.filter(
            employee_id=order.employee_id
        ).first()
        
        if user_profile and user_profile.role:
            plan = CompensationPlan.objects.filter(
                role=user_profile.role,
                status='Active'
            ).first()

    if not plan:
        return None

    commission_amount = Decimal("0.00")

    # RATE-based calculation
    if plan.commission_table_type == 'RATE':
        tier = SCRateTable.objects.filter(
            compensation_plan=plan,
            is_active=True,
            from_amount__lte=order.sales_amount
        ).filter(
            models.Q(to_amount__gte=order.sales_amount) |
            models.Q(to_amount__isnull=True)
        ).order_by('sequence').first()

        if tier:
            commission_amount = (
                order.sales_amount *
                tier.commission_rate /
                Decimal("100")
            ) + tier.bonus_amount

    # FLAT-rate calculation
    elif plan.commission_table_type == 'FLAT':
        flat = SCFlatRateTable.objects.filter(
            compensation_plan=plan,
            is_active=True,
            minimum_sales_threshold__lte=order.sales_amount
        ).first()

        if flat:
            commission_amount = (
                order.sales_amount *
                flat.flat_rate /
                Decimal("100")
            ) + flat.bonus_amount

    if commission_amount <= 0:
        return None

    # Find or create employee
    employee, _ = Employee.objects.get_or_create(
        email=f"{order.employee_id}@company.com",
        defaults={
            "name": order.position_name or order.employee_id
        }
    )

    # Create sale record
    sale = Sale.objects.create(
        employee=employee,
        employee_salary=Decimal("0.00"),
        amount=order.sales_amount
    )

    # Create commission record
    commission = Commission.objects.create(
        employee=employee,
        sale=sale,
        commission_amount=commission_amount
    )

    return commission