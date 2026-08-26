"""Transparent INR cost and expected-profit calculations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from math import ceil
from typing import Iterable

from app.optimizer.domain import Order, PlanningProblem, ScheduleResult, ScheduleTask


@dataclass(frozen=True, slots=True)
class OrderFinancial:
    order_id: str
    revenue: float
    material_cost: float
    regular_labour_cost: float
    overtime_cost: float
    machine_cost: float
    grid_energy_cost: float
    generator_cost: float
    changeover_cost: float
    expected_rework_cost: float
    late_penalty: float
    completion_at: datetime | None
    lateness_minutes: int
    expected_profit: float

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["completion_at"] = self.completion_at.isoformat() if self.completion_at else None
        return result


@dataclass(frozen=True, slots=True)
class FinancialSummary:
    currency: str = "INR"
    revenue: float = 0.0
    material_cost: float = 0.0
    regular_labour_cost: float = 0.0
    overtime_cost: float = 0.0
    machine_operating_cost: float = 0.0
    grid_energy_cost: float = 0.0
    generator_cost: float = 0.0
    changeover_cost: float = 0.0
    maintenance_cost: float = 0.0
    expected_rework_cost: float = 0.0
    outsourcing_cost: float = 0.0
    late_penalties: float = 0.0
    production_cost: float = 0.0
    total_cost: float = 0.0
    expected_profit: float = 0.0
    contribution_margin: float = 0.0
    on_time_orders: int = 0
    late_orders: int = 0
    on_time_delivery_pct: float = 0.0
    overtime_minutes: int = 0
    generator_minutes: int = 0
    changeover_minutes: int = 0
    by_order: dict[str, OrderFinancial] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["by_order"] = {
            key: value.as_dict() for key, value in self.by_order.items()
        }
        return result


def calculate_schedule_financials(
    problem: PlanningProblem,
    schedule: ScheduleResult | Iterable[ScheduleTask],
) -> FinancialSummary:
    """Calculate schedule economics from task timestamps and configured rates.

    Revenue/material/rework are charged once per order.  Resource costs are
    calculated task-by-task; contractual lateness uses continuous elapsed days,
    while `penalty_for_lateness(..., whole_days=True)` is available for contracts
    that charge each started day.
    """

    tasks = list(schedule.tasks if isinstance(schedule, ScheduleResult) else schedule)
    by_order_tasks: dict[str, list[ScheduleTask]] = {order.id: [] for order in problem.orders}
    for task in tasks:
        by_order_tasks.setdefault(task.order_id, []).append(task)

    order_financials: dict[str, OrderFinancial] = {}
    for order in problem.orders:
        order_tasks = by_order_tasks.get(order.id, [])
        scheduled_operation_ids = {task.operation_id for task in order_tasks}
        route_complete = all(
            operation.id in scheduled_operation_ids for operation in order.operations
        )
        completion = (
            max((task.end for task in order_tasks), default=None)
            if route_complete
            else None
        )
        lateness_minutes = (
            max(0, round((completion - order.due_at).total_seconds() / 60))
            if completion
            else max(
                0,
                round((problem.horizon_end - order.due_at).total_seconds() / 60),
            )
        )
        penalty = penalty_for_lateness(
            order,
            completion if completion is not None else problem.horizon_end,
        )
        regular_labour = 0.0
        overtime = 0.0
        machine_cost = 0.0
        grid_energy = 0.0
        generator = 0.0
        changeover = 0.0
        for task in order_tasks:
            duration_hours = task.duration_minutes / 60
            machine = problem.machine_map.get(task.machine_id)
            if machine is None:
                continue
            labour = duration_hours * problem.costs.regular_labour_per_hour
            if task.is_overtime:
                labour *= problem.costs.overtime_multiplier
                if task.is_sunday:
                    labour *= problem.costs.sunday_multiplier
                overtime += labour
            else:
                if task.is_sunday:
                    labour *= problem.costs.sunday_multiplier
                regular_labour += labour
            machine_cost += duration_hours * machine.hourly_cost
            energy = duration_hours * machine.power_kw
            if task.uses_generator:
                generator += energy * _generator_rate(problem, task)
            else:
                grid_energy += energy * _grid_rate(problem, task)
            changeover += task.changeover_cost + (
                task.changeover_minutes
                / 60
                * problem.costs.changeover_labour_per_hour
            )
        expected_rework = (
            order.quantity
            * order.quality_reject_rate
            * problem.costs.rework_cost_per_unit
            if route_complete
            else 0.0
        )
        recognized_revenue = order.selling_price if route_complete else 0.0
        total_cost = (
            order.material_cost
            + regular_labour
            + overtime
            + machine_cost
            + grid_energy
            + generator
            + changeover
            + expected_rework
            + penalty
        )
        order_financials[order.id] = OrderFinancial(
            order_id=order.id,
            revenue=_money(recognized_revenue),
            material_cost=_money(order.material_cost),
            regular_labour_cost=_money(regular_labour),
            overtime_cost=_money(overtime),
            machine_cost=_money(machine_cost),
            grid_energy_cost=_money(grid_energy),
            generator_cost=_money(generator),
            changeover_cost=_money(changeover),
            expected_rework_cost=_money(expected_rework),
            late_penalty=_money(penalty),
            completion_at=completion,
            lateness_minutes=lateness_minutes,
            expected_profit=_money(recognized_revenue - total_cost),
        )

    maintenance_cost = float(problem.metadata.get("maintenance_cost", 0.0) or 0.0)
    outsourcing_cost = float(problem.metadata.get("outsourcing_cost", 0.0) or 0.0)
    revenue = sum(item.revenue for item in order_financials.values())
    material = sum(item.material_cost for item in order_financials.values())
    regular = sum(item.regular_labour_cost for item in order_financials.values())
    overtime = sum(item.overtime_cost for item in order_financials.values())
    machine = sum(item.machine_cost for item in order_financials.values())
    grid = sum(item.grid_energy_cost for item in order_financials.values())
    generator = sum(item.generator_cost for item in order_financials.values())
    changeover = sum(item.changeover_cost for item in order_financials.values())
    rework = sum(item.expected_rework_cost for item in order_financials.values())
    penalties = sum(item.late_penalty for item in order_financials.values())
    production_cost = (
        material
        + regular
        + overtime
        + machine
        + grid
        + generator
        + changeover
        + maintenance_cost
        + rework
        + outsourcing_cost
    )
    total_cost = production_cost + penalties
    on_time = sum(
        item.completion_at is not None and item.lateness_minutes == 0
        for item in order_financials.values()
    )
    late = len(order_financials) - on_time
    return FinancialSummary(
        revenue=_money(revenue),
        material_cost=_money(material),
        regular_labour_cost=_money(regular),
        overtime_cost=_money(overtime),
        machine_operating_cost=_money(machine),
        grid_energy_cost=_money(grid),
        generator_cost=_money(generator),
        changeover_cost=_money(changeover),
        maintenance_cost=_money(maintenance_cost),
        expected_rework_cost=_money(rework),
        outsourcing_cost=_money(outsourcing_cost),
        late_penalties=_money(penalties),
        production_cost=_money(production_cost),
        total_cost=_money(total_cost),
        expected_profit=_money(revenue - total_cost),
        contribution_margin=_money(revenue - material - production_cost + material),
        on_time_orders=on_time,
        late_orders=late,
        on_time_delivery_pct=round(100 * on_time / len(order_financials), 2)
        if order_financials
        else 0.0,
        overtime_minutes=sum(task.duration_minutes for task in tasks if task.is_overtime),
        generator_minutes=sum(task.duration_minutes for task in tasks if task.uses_generator),
        changeover_minutes=sum(task.changeover_minutes for task in tasks),
        by_order=order_financials,
    )


def penalty_for_lateness(
    order: Order,
    completion_at: datetime | None,
    *,
    whole_days: bool = False,
) -> float:
    if completion_at is None or completion_at <= order.due_at:
        return 0.0
    late_days = (completion_at - order.due_at).total_seconds() / 86_400
    billable_days = ceil(late_days) if whole_days else late_days
    return _money(max(0.0, billable_days * order.late_penalty_per_day))


def calculate_disruption_cost(
    baseline: FinancialSummary,
    revised: FinancialSummary,
    *,
    lost_production_cost: float = 0.0,
) -> dict[str, float]:
    overtime_recovery = max(0.0, revised.overtime_cost - baseline.overtime_cost)
    penalty_increase = max(0.0, revised.late_penalties - baseline.late_penalties)
    extra_changeover = max(0.0, revised.changeover_cost - baseline.changeover_cost)
    extra_generator = max(0.0, revised.generator_cost - baseline.generator_cost)
    total = (
        max(0.0, lost_production_cost)
        + overtime_recovery
        + penalty_increase
        + extra_changeover
        + extra_generator
    )
    return {
        "lost_production": _money(lost_production_cost),
        "overtime_recovery": _money(overtime_recovery),
        "penalty_increase": _money(penalty_increase),
        "extra_changeover": _money(extra_changeover),
        "extra_generator": _money(extra_generator),
        "total_disruption_cost": _money(total),
    }


def _grid_rate(problem: PlanningProblem, task: ScheduleTask) -> float:
    active = [
        event
        for event in problem.power_windows
        if event.start <= task.start and event.end >= task.end and event.grid_available
    ]
    if active and active[-1].grid_cost_per_kwh is not None:
        return float(active[-1].grid_cost_per_kwh)
    return problem.costs.grid_cost_per_kwh


def _generator_rate(problem: PlanningProblem, task: ScheduleTask) -> float:
    active = [
        event
        for event in problem.power_windows
        if event.start <= task.start and event.end >= task.end and not event.grid_available
    ]
    if active and active[-1].generator_cost_per_kwh is not None:
        return float(active[-1].generator_cost_per_kwh)
    return problem.costs.generator_cost_per_kwh


def _money(value: float) -> float:
    return round(float(value) + 1e-10, 2)
