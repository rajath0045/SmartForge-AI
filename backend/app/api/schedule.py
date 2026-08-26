from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import ScheduleMode, ScheduleStatus
from app.models import OrderOperation, ProductionOrder, Schedule, ScheduleOperation

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _camel_metrics(metrics: dict) -> dict:
    keys = {
        "production_cost": "productionCost",
        "overtime_cost": "overtimeCost",
        "late_penalties": "latePenalties",
        "generator_cost": "generatorCost",
        "on_time_delivery_percent": "onTimeDeliveryPercent",
        "expected_profit": "expectedProfit",
        "breakdown_exposure": "breakdownExposure",
    }
    return {keys.get(key, key): value for key, value in metrics.items()}


def _schedule_payload(schedule: Schedule) -> dict:
    operations = []
    for item in schedule.operations:
        routing = item.order_operation
        order = routing.order
        operations.append(
            {
                "id": item.id,
                "orderOperationId": item.order_operation_id,
                "orderId": order.id,
                "partNumber": order.part_number,
                "customer": order.customer.name,
                "customerTier": order.customer.tier.value,
                "operationType": routing.operation_type.value,
                "sequence": routing.sequence,
                "machineId": item.machine_id,
                "operatorId": item.operator_id,
                "startAt": item.start_at,
                "endAt": item.end_at,
                "durationMinutes": item.duration_minutes,
                "quantity": item.quantity,
                "status": item.status.value,
                "shiftId": item.shift_id,
                "isOvertime": item.is_overtime,
                "usesGenerator": item.uses_generator,
                "changeoverMinutes": item.changeover_minutes,
                "operationCost": item.operation_cost,
                "energyCost": item.energy_cost,
                "labourCost": item.labour_cost,
            }
        )
    return {
        "id": schedule.id,
        "name": schedule.name,
        "mode": schedule.mode.value,
        "status": schedule.status.value,
        "horizonStart": schedule.horizon_start,
        "horizonEnd": schedule.horizon_end,
        "generatedAt": schedule.generated_at,
        "solverStatus": schedule.solver_status,
        "objectiveValue": schedule.objective_value,
        "isValid": schedule.is_valid,
        "validationErrors": schedule.validation_errors,
        "metrics": _camel_metrics(schedule.metrics),
        "operations": operations,
    }


def _load_schedule(db: Session, mode: ScheduleMode | None) -> Schedule | None:
    statement = select(Schedule).options(
        selectinload(Schedule.operations)
        .selectinload(ScheduleOperation.order_operation)
        .selectinload(OrderOperation.order)
        .selectinload(ProductionOrder.customer)
    )
    if mode is not None:
        statement = statement.where(Schedule.mode == mode)
    else:
        statement = statement.where(Schedule.status == ScheduleStatus.ACTIVE)
    return db.scalar(statement.order_by(Schedule.generated_at.desc()))


@router.get("")
def get_schedule(
    mode: ScheduleMode | None = None, db: Session = Depends(get_db)
) -> dict:
    schedule = _load_schedule(db, mode)
    if schedule is None:
        raise HTTPException(status_code=404, detail="No schedule has been generated")
    return _schedule_payload(schedule)


@router.get("/comparison/snapshot")
def compare_stored_schedules(db: Session = Depends(get_db)) -> dict:
    """Return persisted demonstration snapshots without running a new solve."""
    schedules = list(db.scalars(select(Schedule).order_by(Schedule.mode)).all())
    return {
        "plans": [
            {
                "id": schedule.id,
                "name": schedule.name,
                "mode": schedule.mode.value,
                "isActive": schedule.status == ScheduleStatus.ACTIVE,
                "isValid": schedule.is_valid,
                **_camel_metrics(schedule.metrics),
            }
            for schedule in schedules
        ],
        "recommendedMode": ScheduleMode.MOST_ROBUST.value,
        "explanation": "The robust plan has the highest risk-adjusted profit while preserving a bottleneck buffer.",
    }
