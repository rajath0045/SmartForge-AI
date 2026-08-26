from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import CustomerTier, OrderStatus, RiskLevel
from app.models import (
    Customer,
    Machine,
    Material,
    OperationMachineEligibility,
    OrderOperation,
    PartFamily,
    ProductionOrder,
)
from app.schemas.order import OrderCreate, OrderDetail, OrderSummary

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_options():
    return (
        selectinload(ProductionOrder.customer),
        selectinload(ProductionOrder.part_family),
        selectinload(ProductionOrder.operations).selectinload(
            OrderOperation.eligible_machines
        ),
    )


@router.get("", response_model=list[OrderSummary])
def list_orders(
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    risk_level: RiskLevel | None = None,
    customer_tier: CustomerTier | None = None,
    search: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
) -> list[ProductionOrder]:
    statement = select(ProductionOrder).options(*_order_options())
    if order_status is not None:
        statement = statement.where(ProductionOrder.status == order_status)
    if risk_level is not None:
        statement = statement.where(ProductionOrder.risk_level == risk_level)
    if customer_tier is not None:
        statement = statement.join(ProductionOrder.customer).where(
            Customer.tier == customer_tier
        )
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                ProductionOrder.id.ilike(pattern),
                ProductionOrder.part_number.ilike(pattern),
                ProductionOrder.description.ilike(pattern),
            )
        )
    statement = statement.order_by(ProductionOrder.due_date, ProductionOrder.id)
    return list(db.scalars(statement).unique().all())


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: str, db: Session = Depends(get_db)) -> ProductionOrder:
    order = db.scalar(
        select(ProductionOrder)
        .where(ProductionOrder.id == order_id)
        .options(*_order_options())
    )
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} was not found")
    return order


@router.post("", response_model=OrderDetail, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate, db: Session = Depends(get_db)
) -> ProductionOrder:
    customer = db.get(Customer, payload.customer_id)
    family = db.get(PartFamily, payload.part_family_id)
    if customer is None:
        raise HTTPException(status_code=422, detail="Unknown customerId")
    if family is None:
        raise HTTPException(status_code=422, detail="Unknown partFamilyId")
    if db.get(Material, payload.material_id) is None:
        raise HTTPException(status_code=422, detail="Unknown materialId")

    last_id = db.scalar(select(func.max(ProductionOrder.id))) or "ORD-000"
    try:
        next_number = int(last_id.split("-")[-1]) + 1
    except ValueError:
        next_number = (
            db.scalar(select(func.count()).select_from(ProductionOrder)) or 0
        ) + 1
    order_id = f"ORD-{next_number:03d}"
    order = ProductionOrder(
        id=order_id,
        customer_id=payload.customer_id,
        part_family_id=payload.part_family_id,
        part_number=payload.part_number,
        description=payload.description,
        quantity=payload.quantity,
        due_date=payload.due_date,
        promised_date=payload.due_date,
        status=OrderStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        priority=payload.priority,
        unit_selling_price=payload.unit_selling_price,
        unit_material_cost=payload.unit_material_cost,
        expected_production_cost=0.0,
        late_penalty_per_day=payload.late_penalty_per_day,
        material_id=payload.material_id,
        material_required_qty=payload.material_required_qty,
        material_available_date=payload.material_available_date,
        quality_reject_rate=payload.quality_reject_rate,
        delivery_probability=0.90,
    )
    previous: OrderOperation | None = None
    estimated_cost = 0.0
    for sequence, operation_payload in enumerate(payload.operations, start=1):
        eligible_machines = list(
            db.scalars(
                select(Machine)
                .where(Machine.machine_type == operation_payload.required_machine_type)
                .order_by(Machine.health_score.desc())
            ).all()
        )
        if not eligible_machines:
            raise HTTPException(
                status_code=422,
                detail=f"No machine supports {operation_payload.required_machine_type.value}",
            )
        operation = OrderOperation(
            sequence=sequence,
            operation_type=operation_payload.operation_type,
            required_machine_type=operation_payload.required_machine_type,
            required_skill=operation_payload.operation_type,
            setup_minutes=operation_payload.setup_minutes,
            run_minutes_per_unit=operation_payload.run_minutes_per_unit,
            batch_size=operation_payload.batch_size,
            planned_quantity=payload.quantity,
            predecessor=previous,
            outsource_allowed=operation_payload.outsource_allowed,
        )
        for rank, machine in enumerate(eligible_machines, start=1):
            operation.eligible_machines.append(
                OperationMachineEligibility(machine_id=machine.id, preference_rank=rank)
            )
        average_machine_cost = sum(
            machine.hourly_cost for machine in eligible_machines
        ) / len(eligible_machines)
        hours = operation.processing_minutes / 60
        estimated_cost += hours * (average_machine_cost + 240.0)
        order.operations.append(operation)
        previous = operation
    order.expected_production_cost = round(estimated_cost, 2)
    estimated_hours = (
        sum(operation.processing_minutes for operation in order.operations) / 60
    )
    slack_hours = (
        payload.due_date - payload.material_available_date
    ).total_seconds() / 3600
    order.delivery_probability = round(
        max(0.45, min(0.98, 0.98 - max(0, estimated_hours - slack_hours) / 100)), 2
    )
    if order.delivery_probability < 0.7:
        order.risk_level = RiskLevel.HIGH
        order.status = OrderStatus.AT_RISK
    order.expected_completion_at = payload.material_available_date + timedelta(
        hours=estimated_hours
    )

    db.add(order)
    db.commit()
    return get_order(order_id, db)
