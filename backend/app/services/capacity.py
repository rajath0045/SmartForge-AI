"""Finite capacity and Theory-of-Constraints style bottleneck analytics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable

from app.optimizer.domain import PlanningProblem, ScheduleResult, ScheduleTask


@dataclass(frozen=True, slots=True)
class ResourceCapacity:
    resource_id: str
    resource_type: str
    available_minutes: int
    committed_minutes: int
    remaining_minutes: int
    predicted_minutes: int
    utilization_pct: float
    queue_minutes: int
    status: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BottleneckAnalysis:
    machine_id: str | None
    machine_type: str | None
    utilization_pct: float
    queue_hours: float
    dependent_orders: tuple[str, ...]
    tier_1_orders: tuple[str, ...]
    dependent_revenue: float
    explanation: str
    recommendations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def calculate_machine_capacity(
    problem: PlanningProblem,
    schedule: ScheduleResult | Iterable[ScheduleTask],
) -> list[ResourceCapacity]:
    tasks = list(schedule.tasks if isinstance(schedule, ScheduleResult) else schedule)
    capacities: list[ResourceCapacity] = []
    for machine in problem.machines:
        calendar_minutes = _union_minutes(
            (max(problem.horizon_start, shift.start), min(problem.horizon_end, shift.end))
            for shift in problem.shifts
            if shift.end > problem.horizon_start
            and shift.start < problem.horizon_end
            and (problem.allow_overtime or not shift.is_overtime)
            and _has_qualified_operator(problem, machine.id, shift.start, shift.end)
        )
        downtime = _union_minutes(
            (max(problem.horizon_start, window.start), min(problem.horizon_end, window.end))
            for window in machine.unavailable
            if window.end > problem.horizon_start and window.start < problem.horizon_end
        )
        available = max(0, calendar_minutes - min(calendar_minutes, downtime))
        machine_tasks = [task for task in tasks if task.machine_id == machine.id]
        committed = sum(
            task.duration_minutes
            + task.robust_buffer_minutes
            + task.changeover_minutes
            for task in machine_tasks
        )
        queue = sum(
            operation.duration_minutes
            for order in problem.orders
            for operation in order.operations
            if machine.can_process(operation.operation_type)
            and not any(task.operation_id == operation.id for task in machine_tasks)
        )
        predicted = round(available * (1 - min(0.95, max(0.0, machine.failure_probability))))
        utilization = 100 * committed / available if available else (100.0 if committed else 0.0)
        capacities.append(
            ResourceCapacity(
                resource_id=machine.id,
                resource_type=machine.machine_type,
                available_minutes=available,
                committed_minutes=committed,
                remaining_minutes=max(0, available - committed),
                predicted_minutes=max(0, predicted),
                utilization_pct=round(utilization, 1),
                queue_minutes=queue,
                status=_capacity_status(utilization),
            )
        )
    return sorted(capacities, key=lambda item: (-item.utilization_pct, item.resource_id))


def calculate_skill_capacity(problem: PlanningProblem) -> list[dict[str, object]]:
    skills = sorted(
        {skill for operator in problem.operators for skill in operator.skills}
        | {
            operation.skill
            for order in problem.orders
            for operation in order.operations
        }
    )
    rows: list[dict[str, object]] = []
    for skill in skills:
        qualified = [
            operator
            for operator in problem.operators
            if str(skill).upper() in {str(item).upper() for item in operator.skills}
        ]
        minutes = sum(
            max(0, round((window.end - window.start).total_seconds() / 60))
            for operator in qualified
            for window in (operator.availability or problem.shifts)
            if window.end > problem.horizon_start and window.start < problem.horizon_end
        )
        demand = sum(
            operation.duration_minutes
            for order in problem.orders
            for operation in order.operations
            if str(operation.skill).upper() == str(skill).upper()
        )
        utilization = 100 * demand / minutes if minutes else (100.0 if demand else 0.0)
        rows.append(
            {
                "skill": str(skill),
                "qualified_operators": len(qualified),
                "available_minutes": minutes,
                "demand_minutes": demand,
                "utilization_pct": round(utilization, 1),
                "status": _capacity_status(utilization),
            }
        )
    return rows


def identify_bottleneck(
    problem: PlanningProblem,
    schedule: ScheduleResult | Iterable[ScheduleTask],
) -> BottleneckAnalysis:
    tasks = list(schedule.tasks if isinstance(schedule, ScheduleResult) else schedule)
    capacities = calculate_machine_capacity(problem, tasks)
    if not capacities:
        return BottleneckAnalysis(
            None, None, 0.0, 0.0, (), (), 0.0, "No machines configured", ()
        )
    def protected_load(item: ResourceCapacity) -> float:
        machine = problem.machine_map[item.resource_id]
        # Promiseable capacity is smaller than the raw shift calendar. Expected
        # failure removes predicted hours, and fragile/single-point equipment
        # must retain recovery reserve instead of being loaded to its forecast
        # maximum. Both inputs remain visible and deterministic.
        reserve_ratio = (
            0.15
            if machine.failure_probability >= 0.15 or machine.health_score < 80
            else 0.05
        )
        protected_minutes = max(
            1.0,
            item.predicted_minutes * (1 - reserve_ratio),
        )
        return 100 * item.committed_minutes / protected_minutes

    bottleneck = max(
        capacities,
        key=lambda item: (
            protected_load(item),
            item.queue_minutes,
            item.committed_minutes,
        ),
    )
    protected_utilization = round(protected_load(bottleneck), 1)
    affected_task_orders = {
        task.order_id for task in tasks if task.machine_id == bottleneck.resource_id
    }
    machine = problem.machine_map[bottleneck.resource_id]
    affected_task_orders.update(
        operation.order_id
        for order in problem.orders
        for operation in order.operations
        if machine.can_process(operation.operation_type)
    )
    order_map = problem.order_map
    tier_1 = tuple(
        sorted(
            order_id
            for order_id in affected_task_orders
            if _is_tier_1(order_map[order_id].customer_tier)
        )
    )
    revenue = sum(order_map[order_id].selling_price for order_id in affected_task_orders)
    recommendations = [
        f"Protect {machine.id} from non-bottleneck idle time and group compatible part families",
    ]
    if protected_utilization >= 90:
        recommendations.append(
            "Evaluate targeted overtime or outsourcing to restore protected "
            f"reserve; health-adjusted loading is {protected_utilization:.1f}%"
        )
    if machine.health_score < 75:
        recommendations.append(
            f"Schedule preventive maintenance; {machine.id} health is {machine.health_score:.0f}/100"
        )
    return BottleneckAnalysis(
        machine_id=machine.id,
        machine_type=machine.machine_type,
        utilization_pct=protected_utilization,
        queue_hours=round(bottleneck.queue_minutes / 60, 1),
        dependent_orders=tuple(sorted(affected_task_orders)),
        tier_1_orders=tier_1,
        dependent_revenue=round(revenue, 2),
        explanation=(
            f"{machine.id} is the current constraint at {protected_utilization:.1f}% "
            f"health-adjusted finite-capacity loading with {bottleneck.queue_minutes / 60:.1f} queued hours; "
            f"₹{revenue:,.0f} of order revenue depends on its capability."
        ),
        recommendations=tuple(recommendations),
    )


def _has_qualified_operator(
    problem: PlanningProblem,
    machine_id: str,
    start: datetime,
    end: datetime,
) -> bool:
    machine = problem.machine_map[machine_id]
    for operator in problem.operators:
        if not any(
            operator.is_qualified(machine, capability)
            for capability in machine.capabilities
        ):
            continue
        if not operator.availability or any(
            window.start < end and window.end > start for window in operator.availability
        ):
            return True
    return False


def _union_minutes(intervals: Iterable[tuple[datetime, datetime]]) -> int:
    ordered = sorted((start, end) for start, end in intervals if end > start)
    if not ordered:
        return 0
    total = 0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += round((current_end - current_start).total_seconds() / 60)
            current_start, current_end = start, end
    total += round((current_end - current_start).total_seconds() / 60)
    return max(0, total)


def _capacity_status(utilization: float) -> str:
    if utilization >= 95:
        return "CRITICAL"
    if utilization >= 85:
        return "HIGH"
    if utilization >= 70:
        return "WATCH"
    return "HEALTHY"


def _is_tier_1(tier: str) -> bool:
    return str(getattr(tier, "value", tier)).upper().replace("-", "_") in {
        "TIER_1",
        "TIER1",
    }
