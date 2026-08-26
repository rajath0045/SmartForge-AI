from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import (
    DisruptionStatus,
    MachineStatus,
    OrderStatus,
    RecommendationStatus,
    RiskLevel,
    ScheduleStatus,
)
from app.models import (
    Disruption,
    Inventory,
    Machine,
    Operator,
    PowerEvent,
    ProductionOrder,
    QualityEvent,
    Recommendation,
    Schedule,
)
from app.schemas.dashboard import (
    BottleneckSummary,
    DashboardAlert,
    DashboardKPI,
    DashboardRead,
    FactoryStatus,
)
from app.seed import DEMO_NOW

from .metrics import capacity_snapshot

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    machines = list(db.scalars(select(Machine)).all())
    operators = list(db.scalars(select(Operator)).all())
    orders = list(
        db.scalars(
            select(ProductionOrder).options(selectinload(ProductionOrder.customer))
        ).all()
    )
    schedule = db.scalar(
        select(Schedule)
        .where(Schedule.status == ScheduleStatus.ACTIVE)
        .options(selectinload(Schedule.operations))
        .order_by(Schedule.generated_at.desc())
    )
    quality_events = list(db.scalars(select(QualityEvent)).all())
    power_event = db.scalar(
        select(PowerEvent).where(
            PowerEvent.start_at <= DEMO_NOW,
            PowerEvent.end_at >= DEMO_NOW,
        )
    )
    capacity = capacity_snapshot(db)

    active_orders = [order for order in orders if order.status != OrderStatus.COMPLETED]
    completed_orders = [
        order for order in orders if order.status == OrderStatus.COMPLETED
    ]
    risk_orders = [order for order in orders if order.status == OrderStatus.AT_RISK]
    delayed_orders = [order for order in orders if order.status == OrderStatus.DELAYED]
    revenue = sum(order.revenue for order in orders)
    production_cost = sum(
        order.material_cost + order.expected_production_cost for order in orders
    )
    expected_penalties = sum(
        order.late_penalty_per_day * max(0.0, 1 - order.delivery_probability)
        for order in active_orders
    )
    expected_profit = (
        sum(order.expected_profit for order in orders) - expected_penalties
    )
    schedule_operations = schedule.operations if schedule else []
    overtime_cost = sum(
        operation.labour_cost * 0.5
        for operation in schedule_operations
        if operation.is_overtime
    )
    energy_cost = sum(operation.energy_cost for operation in schedule_operations)
    generator_cost = sum(
        operation.energy_cost * (28.5 / 8.4)
        for operation in schedule_operations
        if operation.uses_generator
    )
    changeover_losses = sum(
        operation.changeover_minutes / 60 * 1_100 for operation in schedule_operations
    )
    rework_cost = sum(event.rework_cost for event in quality_events)
    capacity_rows = capacity["by_machine_type"]
    total_available = sum(row["available_hours"] for row in capacity_rows)
    total_committed = sum(row["committed_hours"] for row in capacity_rows)
    machine_utilization = (
        total_committed / total_available * 100 if total_available else 0.0
    )
    present_operators = [
        operator for operator in operators if operator.status.value == "AVAILABLE"
    ]
    labour_capacity = len(present_operators) * capacity["working_days"] * 8
    labour_utilization = (
        min(100.0, total_committed / labour_capacity * 100) if labour_capacity else 0.0
    )
    average_oee = (
        sum(machine.oee for machine in machines) / len(machines) if machines else 0.0
    )
    on_time_delivery = (
        float(schedule.metrics.get("on_time_delivery_percent", 0.0))
        if schedule
        else 0.0
    )
    # Count stock positions at or below safety stock without materializing an ERP-style aggregate.
    inventory_records = list(db.scalars(select(Inventory)).all())
    material_shortages = sum(
        record.available_quantity <= record.safety_stock_quantity
        for record in inventory_records
    )

    bottleneck_type = capacity["bottleneck"] or {
        "machine_type": "N/A",
        "utilization_percent": 0.0,
        "committed_hours": 0.0,
        "available_hours": 0.0,
        "dependent_orders": 0,
        "status": "HEALTHY",
    }
    bottleneck_machine = next(
        (
            item
            for item in capacity["by_machine"]
            if item["machine_type"] == bottleneck_type["machine_type"]
        ),
        {
            "machine_id": "N/A",
            "machine_name": bottleneck_type["machine_type"].replace("_", " ").title(),
        },
    )

    severity_rank = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 3,
    }
    disruptions = list(
        db.scalars(
            select(Disruption).where(Disruption.status != DisruptionStatus.RESOLVED)
        ).all()
    )
    disruptions.sort(key=lambda item: (severity_rank[item.severity], item.start_at))
    recommendations = list(
        db.scalars(
            select(Recommendation).where(
                Recommendation.status == RecommendationStatus.PENDING
            )
        ).all()
    )
    recommendations.sort(key=lambda item: severity_rank[item.severity])
    alerts = [
        DashboardAlert(
            id=f"DIS-{item.id}",
            severity=item.severity.value,
            category=item.disruption_type.value,
            title=item.title,
            description=item.description,
            affected_resource=item.machine_id
            or item.operator_id
            or item.order_id
            or item.material_id,
            estimated_financial_impact=item.estimated_financial_impact,
            recommended_action="Open Disruption Control and approve the recovery plan.",
        )
        for item in disruptions[:3]
    ]
    alerts.extend(
        DashboardAlert(
            id=f"REC-{item.id}",
            severity=item.severity.value,
            category=item.category,
            title=item.title,
            description=item.explanation,
            affected_resource=item.machine_id or item.order_id,
            estimated_financial_impact=max(
                0.0, item.financial_benefit - item.estimated_cost
            ),
            recommended_action=item.recommended_action,
        )
        for item in recommendations[: max(0, 5 - len(alerts))]
    )

    return DashboardRead(
        as_of=DEMO_NOW,
        factory_name="Sridhar Precision Works — Hosur",
        kpis=DashboardKPI(
            active_orders=len(active_orders),
            completed_orders=len(completed_orders),
            orders_at_risk=len(risk_orders),
            delayed_orders=len(delayed_orders),
            on_time_delivery_percent=round(on_time_delivery, 1),
            machine_utilization_percent=round(machine_utilization, 1),
            oee_percent=round(average_oee, 1),
            labour_utilization_percent=round(labour_utilization, 1),
            bottleneck_utilization_percent=round(
                bottleneck_type["utilization_percent"], 1
            ),
            production_cost=round(production_cost, 2),
            revenue=round(revenue, 2),
            expected_profit=round(expected_profit, 2),
            overtime_cost=round(overtime_cost, 2),
            late_penalties=round(expected_penalties, 2),
            energy_cost=round(energy_cost, 2),
            generator_cost=round(generator_cost, 2),
            changeover_losses=round(changeover_losses, 2),
            rework_cost=round(rework_cost, 2),
        ),
        factory_status=FactoryStatus(
            machines_running=sum(
                machine.status == MachineStatus.RUNNING for machine in machines
            ),
            machines_idle=sum(
                machine.status == MachineStatus.IDLE for machine in machines
            ),
            machines_setup=sum(
                machine.status == MachineStatus.SETUP for machine in machines
            ),
            machines_maintenance=sum(
                machine.status == MachineStatus.MAINTENANCE for machine in machines
            ),
            machines_broken=sum(
                machine.status == MachineStatus.BREAKDOWN for machine in machines
            ),
            operators_present=len(present_operators),
            operators_absent=len(operators) - len(present_operators),
            grid_power_status=(
                "AVAILABLE"
                if power_event is None or power_event.grid_available
                else "OUTAGE"
            ),
            generator_status=(
                "READY"
                if power_event is None or power_event.generator_available
                else "UNAVAILABLE"
            ),
            material_shortages=material_shortages,
        ),
        bottleneck=BottleneckSummary(
            machine_id=bottleneck_machine["machine_id"],
            machine_name=bottleneck_machine["machine_name"],
            utilization_percent=bottleneck_type["utilization_percent"],
            committed_hours=bottleneck_type["committed_hours"],
            available_hours=bottleneck_type["available_hours"],
            dependent_orders=bottleneck_type["dependent_orders"],
            status=bottleneck_type["status"],
        ),
        action_required=alerts,
    )
