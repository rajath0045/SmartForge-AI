from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import MachineStatus, MachineType, OrderStatus
from app.models import Machine, ProductionOrder
from app.seed import HORIZON_END, HORIZON_START

WORKING_DAYS = sum(
    1
    for day in range((HORIZON_END - HORIZON_START).days)
    if (HORIZON_START + timedelta(days=day)).weekday() != 6
)
REGULAR_HOURS_PER_DAY = 16.0


def capacity_snapshot(db: Session) -> dict:
    machines = list(db.scalars(select(Machine)).all())
    orders = list(
        db.scalars(
            select(ProductionOrder)
            .where(ProductionOrder.status != OrderStatus.COMPLETED)
            .options(selectinload(ProductionOrder.operations))
        ).all()
    )
    committed_by_type: dict[MachineType, float] = defaultdict(float)
    dependent_orders: dict[MachineType, set[str]] = defaultdict(set)
    for order in orders:
        for operation in order.operations:
            committed_by_type[operation.required_machine_type] += (
                operation.processing_minutes / 60
            )
            dependent_orders[operation.required_machine_type].add(order.id)

    by_type: list[dict] = []
    for machine_type in MachineType:
        type_machines = [
            machine for machine in machines if machine.machine_type == machine_type
        ]
        if not type_machines:
            continue
        nominal = len(type_machines) * WORKING_DAYS * REGULAR_HOURS_PER_DAY
        availability_factor = sum(
            machine.availability_rate for machine in type_machines
        ) / len(type_machines)
        unavailable_factor = sum(
            1
            for machine in type_machines
            if machine.status in {MachineStatus.BREAKDOWN, MachineStatus.MAINTENANCE}
        ) / len(type_machines)
        available = nominal * availability_factor * (1 - unavailable_factor * 0.18)
        committed = committed_by_type[machine_type]
        utilization = committed / available * 100 if available else 0.0
        by_type.append(
            {
                "machine_type": machine_type.value,
                "machine_count": len(type_machines),
                "available_hours": round(available, 1),
                "committed_hours": round(committed, 1),
                "remaining_hours": round(available - committed, 1),
                "utilization_percent": round(utilization, 1),
                "dependent_orders": len(dependent_orders[machine_type]),
                "status": "CRITICAL"
                if utilization >= 90
                else "TIGHT"
                if utilization >= 78
                else "HEALTHY",
            }
        )

    by_machine: list[dict] = []
    for machine in machines:
        type_total_capacity = next(
            row["available_hours"]
            for row in by_type
            if row["machine_type"] == machine.machine_type.value
        )
        peers = sum(1 for peer in machines if peer.machine_type == machine.machine_type)
        available = type_total_capacity / peers
        # Aggregate commitments are apportioned by capability efficiency for a useful resource view.
        peer_efficiency = (
            sum(
                capability.efficiency
                for peer in machines
                if peer.machine_type == machine.machine_type
                for capability in peer.capabilities
                if capability.operation_type.value != "REWORK"
            )
            or peers
        )
        machine_efficiency = (
            sum(
                capability.efficiency
                for capability in machine.capabilities
                if capability.operation_type.value != "REWORK"
            )
            or 1.0
        )
        committed = (
            committed_by_type[machine.machine_type]
            * machine_efficiency
            / peer_efficiency
        )
        utilization = committed / available * 100 if available else 0.0
        by_machine.append(
            {
                "machine_id": machine.id,
                "machine_name": machine.name,
                "machine_type": machine.machine_type.value,
                "status": machine.status.value,
                "available_hours": round(available, 1),
                "committed_hours": round(committed, 1),
                "remaining_hours": round(available - committed, 1),
                "utilization_percent": round(utilization, 1),
                "health_score": machine.health_score,
            }
        )

    by_type.sort(key=lambda row: row["utilization_percent"], reverse=True)
    by_machine.sort(key=lambda row: row["utilization_percent"], reverse=True)
    bottleneck = by_type[0] if by_type else None
    return {
        "horizon_start": HORIZON_START,
        "horizon_end": HORIZON_END,
        "working_days": WORKING_DAYS,
        "bottleneck": bottleneck,
        "by_machine_type": by_type,
        "by_machine": by_machine,
    }
