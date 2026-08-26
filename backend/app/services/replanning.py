"""Disruption application, frozen-work replanning, and schedule diffs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Mapping

from app.optimizer.domain import (
    CalendarWindow,
    Operation,
    PlanningProblem,
    PowerWindow,
    ScheduleMode,
    ScheduleResult,
    ScheduleTask,
)
from app.optimizer.scheduler import SchedulingEngine

from .financial import calculate_disruption_cost, calculate_schedule_financials


class DisruptionKind(StrEnum):
    MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN"
    OPERATOR_ABSENCE = "OPERATOR_ABSENCE"
    MATERIAL_DELAY = "MATERIAL_DELAY"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    POWER_CUT = "POWER_CUT"


@dataclass(frozen=True, slots=True)
class DisruptionEvent:
    kind: DisruptionKind
    start_at: datetime
    end_at: datetime | None = None
    machine_id: str | None = None
    operator_id: str | None = None
    order_id: str | None = None
    generator_available: bool = False
    generator_capacity_kw: float = 0.0
    rejected_quantity: int = 0
    operation_type: str | None = None
    rework_minutes: int | None = None
    description: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DisruptionEvent":
        kind = DisruptionKind(str(getattr(value.get("kind") or value.get("type"), "value", value.get("kind") or value.get("type"))).upper())
        return cls(
            kind=kind,
            start_at=_datetime(value.get("start_at") or value.get("start")),
            end_at=_optional_datetime(value.get("end_at") or value.get("end")),
            machine_id=value.get("machine_id"),
            operator_id=value.get("operator_id"),
            order_id=value.get("order_id"),
            generator_available=bool(value.get("generator_available", False)),
            generator_capacity_kw=float(value.get("generator_capacity_kw", 0.0) or 0.0),
            rejected_quantity=int(value.get("rejected_quantity", 0) or 0),
            operation_type=value.get("operation_type"),
            rework_minutes=(
                int(value["rework_minutes"])
                if value.get("rework_minutes") is not None
                else None
            ),
            description=str(value.get("description", "")),
        )


@dataclass(frozen=True, slots=True)
class TaskChange:
    operation_id: str
    order_id: str
    old_start: datetime | None
    new_start: datetime | None
    old_machine_id: str | None
    new_machine_id: str | None
    old_shift: str | None
    new_shift: str | None
    change_type: str

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in ("old_start", "new_start"):
            if data[key] is not None:
                data[key] = data[key].isoformat()
        return data


@dataclass(slots=True)
class ScheduleDiff:
    changes: list[TaskChange]
    jobs_moved: int
    machine_changes: int
    shift_changes: int
    new_overtime_minutes: int
    new_generator_minutes: int
    deliveries_now_at_risk: list[str]
    new_completion_dates: dict[str, datetime]
    cost_impact: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "changes": [change.as_dict() for change in self.changes],
            "jobs_moved": self.jobs_moved,
            "machine_changes": self.machine_changes,
            "shift_changes": self.shift_changes,
            "new_overtime_minutes": self.new_overtime_minutes,
            "new_generator_minutes": self.new_generator_minutes,
            "deliveries_now_at_risk": self.deliveries_now_at_risk,
            "new_completion_dates": {
                key: value.isoformat() for key, value in self.new_completion_dates.items()
            },
            "cost_impact": self.cost_impact,
        }


@dataclass(slots=True)
class ReplanResult:
    disruption: DisruptionEvent
    revised_problem: PlanningProblem
    previous_schedule: ScheduleResult
    revised_schedule: ScheduleResult
    difference: ScheduleDiff
    frozen_task_ids: tuple[str, ...]
    explanation: str

    def as_dict(self, *, include_schedule: bool = False) -> dict[str, object]:
        data: dict[str, object] = {
            "disruption": asdict(self.disruption),
            "difference": self.difference.as_dict(),
            "frozen_task_ids": self.frozen_task_ids,
            "explanation": self.explanation,
        }
        data["disruption"]["kind"] = self.disruption.kind.value
        data["disruption"]["start_at"] = self.disruption.start_at.isoformat()
        if self.disruption.end_at:
            data["disruption"]["end_at"] = self.disruption.end_at.isoformat()
        if include_schedule:
            data["revised_schedule"] = self.revised_schedule
        return data


class ReplanningService:
    def __init__(self, engine: SchedulingEngine | None = None) -> None:
        self.engine = engine or SchedulingEngine()

    def replan(
        self,
        problem: PlanningProblem,
        previous_schedule: ScheduleResult,
        disruption: DisruptionEvent | Mapping[str, Any],
        *,
        mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
    ) -> ReplanResult:
        event = (
            disruption
            if isinstance(disruption, DisruptionEvent)
            else DisruptionEvent.from_mapping(disruption)
        )
        if not (problem.horizon_start <= event.start_at < problem.horizon_end):
            raise ValueError("disruption start must be inside the planning horizon")
        event_end = event.end_at or event.start_at
        if event_end < event.start_at:
            raise ValueError("disruption end cannot precede start")

        fixed: list[ScheduleTask] = []
        for task in previous_schedule.tasks:
            completed = task.end <= event.start_at
            in_progress = task.start < event.start_at < task.end
            affected_in_progress = (
                event.kind == DisruptionKind.MACHINE_BREAKDOWN
                and event.machine_id == task.machine_id
            ) or (
                event.kind == DisruptionKind.OPERATOR_ABSENCE
                and event.operator_id == task.operator_id
            ) or (
                # A grid outage changes the feasible power source for every
                # running machine.  Re-solve intersecting work so generator
                # capacity and cost are modeled instead of freezing a task
                # that still claims normal grid power.
                event.kind == DisruptionKind.POWER_CUT
            )
            if completed or (in_progress and not affected_in_progress):
                fixed.append(replace(task, is_frozen=True))

        revised = self._apply_event(problem, event, tuple(fixed))
        revised_schedule = self.engine.generate(revised, mode)
        difference = compare_schedules(
            problem,
            previous_schedule,
            revised,
            revised_schedule,
            event,
        )
        explanation = (
            f"Frozen {len(fixed)} completed/unaffected in-progress operations and rescheduled the remainder. "
            f"{difference.jobs_moved} jobs moved; modeled disruption cost is "
            f"₹{difference.cost_impact['total_disruption_cost']:,.0f}."
        )
        return ReplanResult(
            disruption=event,
            revised_problem=revised,
            previous_schedule=previous_schedule,
            revised_schedule=revised_schedule,
            difference=difference,
            frozen_task_ids=tuple(task.id for task in fixed),
            explanation=explanation,
        )

    def _apply_event(
        self,
        problem: PlanningProblem,
        event: DisruptionEvent,
        fixed: tuple[ScheduleTask, ...],
    ) -> PlanningProblem:
        machines = problem.machines
        operators = problem.operators
        orders = problem.orders
        power = problem.power_windows
        end = event.end_at or event.start_at

        if event.kind == DisruptionKind.MACHINE_BREAKDOWN:
            if not event.machine_id or event.machine_id not in problem.machine_map:
                raise ValueError("machine breakdown requires a valid machine_id")
            if end <= event.start_at:
                raise ValueError("machine breakdown requires a positive repair duration")
            machines = tuple(
                replace(
                    machine,
                    unavailable=(
                        *machine.unavailable,
                        CalendarWindow(
                            event.start_at,
                            end,
                            "BREAKDOWN",
                        ),
                    ),
                )
                if machine.id == event.machine_id
                else machine
                for machine in problem.machines
            )
        elif event.kind == DisruptionKind.OPERATOR_ABSENCE:
            if not event.operator_id or event.operator_id not in problem.operator_map:
                raise ValueError("operator absence requires a valid operator_id")
            if end <= event.start_at:
                raise ValueError("operator absence requires a positive duration")
            operators = tuple(
                replace(
                    operator,
                    availability=tuple(
                        segment
                        for window in (operator.availability or problem.shifts)
                        for segment in _subtract_window(window, event.start_at, end)
                    ),
                )
                if operator.id == event.operator_id
                else operator
                for operator in problem.operators
            )
        elif event.kind == DisruptionKind.MATERIAL_DELAY:
            if not event.order_id or event.order_id not in problem.order_map:
                raise ValueError("material delay requires a valid order_id")
            orders = tuple(
                replace(order, release_at=max(order.release_at or problem.horizon_start, end))
                if order.id == event.order_id
                else order
                for order in problem.orders
            )
        elif event.kind == DisruptionKind.POWER_CUT:
            if end <= event.start_at:
                raise ValueError("power cut requires a positive duration")
            power = (
                *problem.power_windows,
                PowerWindow(
                    event.start_at,
                    end,
                    grid_available=False,
                    generator_available=event.generator_available,
                    generator_capacity_kw=event.generator_capacity_kw,
                    name="DISRUPTION_POWER_CUT",
                ),
            )
        elif event.kind == DisruptionKind.QUALITY_FAILURE:
            if not event.order_id or event.order_id not in problem.order_map:
                raise ValueError("quality failure requires a valid order_id")
            if event.rejected_quantity <= 0:
                raise ValueError("quality failure requires rejected_quantity > 0")
            orders = tuple(
                _append_rework(order, event)
                if order.id == event.order_id
                else order
                for order in problem.orders
            )
        return replace(
            problem,
            machines=machines,
            operators=operators,
            orders=orders,
            power_windows=power,
            fixed_tasks=fixed,
            metadata={
                **problem.metadata,
                "last_disruption": event.kind.value,
                # Pending work may not be back-scheduled before the event;
                # frozen historical work retains its original material dates.
                "planning_release_at": event.start_at,
            },
        )


def compare_schedules(
    baseline_problem: PlanningProblem,
    baseline: ScheduleResult,
    revised_problem: PlanningProblem,
    revised: ScheduleResult,
    disruption: DisruptionEvent,
) -> ScheduleDiff:
    old = {
        task.operation_id: task
        for task in baseline.tasks
        if task.end > disruption.start_at
    }
    new = {
        task.operation_id: task
        for task in revised.tasks
        if task.end > disruption.start_at
    }
    changes: list[TaskChange] = []
    for operation_id in sorted(set(old) | set(new)):
        before = old.get(operation_id)
        after = new.get(operation_id)
        if before is None:
            change_type = "ADDED"
        elif after is None:
            change_type = "UNSCHEDULED"
        elif (
            before.start == after.start
            and before.machine_id == after.machine_id
            and before.shift_name == after.shift_name
        ):
            continue
        else:
            change_type = "MOVED"
        changes.append(
            TaskChange(
                operation_id=operation_id,
                order_id=(after or before).order_id,  # type: ignore[union-attr]
                old_start=before.start if before else None,
                new_start=after.start if after else None,
                old_machine_id=before.machine_id if before else None,
                new_machine_id=after.machine_id if after else None,
                old_shift=before.shift_name if before else None,
                new_shift=after.shift_name if after else None,
                change_type=change_type,
            )
        )
    baseline_financial = calculate_schedule_financials(
        baseline_problem, baseline.tasks
    )
    revised_financial = calculate_schedule_financials(
        revised_problem, revised.tasks
    )
    baseline_overtime = sum(
        task.duration_minutes
        for task in baseline.tasks
        if task.is_overtime and task.end > disruption.start_at
    )
    revised_overtime = sum(
        task.duration_minutes
        for task in revised.tasks
        if task.is_overtime and task.end > disruption.start_at
    )
    baseline_generator = sum(
        task.duration_minutes
        for task in baseline.tasks
        if task.uses_generator and task.end > disruption.start_at
    )
    revised_generator = sum(
        task.duration_minutes
        for task in revised.tasks
        if task.uses_generator and task.end > disruption.start_at
    )
    completions = {
        order.id: max(
            (task.end for task in revised.tasks if task.order_id == order.id),
            default=problem_default_completion(revised_problem, order.id),
        )
        for order in revised_problem.orders
    }
    at_risk = [
        order.id
        for order in revised_problem.orders
        if completions[order.id] > order.due_at
        and (
            baseline_financial.by_order.get(order.id) is None
            or baseline_financial.by_order[order.id].lateness_minutes == 0
        )
    ]
    lost_production = _lost_production_cost(baseline_problem, disruption)
    cost_impact = calculate_disruption_cost(
        baseline_financial,
        revised_financial,
        lost_production_cost=lost_production,
    )
    return ScheduleDiff(
        changes=changes,
        jobs_moved=sum(change.change_type == "MOVED" for change in changes),
        machine_changes=sum(
            change.old_machine_id is not None
            and change.new_machine_id is not None
            and change.old_machine_id != change.new_machine_id
            for change in changes
        ),
        shift_changes=sum(
            change.old_shift is not None
            and change.new_shift is not None
            and change.old_shift != change.new_shift
            for change in changes
        ),
        new_overtime_minutes=max(0, revised_overtime - baseline_overtime),
        new_generator_minutes=max(0, revised_generator - baseline_generator),
        deliveries_now_at_risk=sorted(at_risk),
        new_completion_dates=completions,
        cost_impact=cost_impact,
    )


def replan_schedule(
    problem: PlanningProblem,
    previous_schedule: ScheduleResult,
    disruption: DisruptionEvent | Mapping[str, Any],
    *,
    mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
    engine: SchedulingEngine | None = None,
) -> ReplanResult:
    return ReplanningService(engine).replan(
        problem, previous_schedule, disruption, mode=mode
    )


def _subtract_window(
    window: CalendarWindow, absent_start: datetime, absent_end: datetime
) -> tuple[CalendarWindow, ...]:
    if window.end <= absent_start or window.start >= absent_end:
        return (window,)
    result: list[CalendarWindow] = []
    if window.start < absent_start:
        result.append(replace(window, end=absent_start))
    if window.end > absent_end:
        result.append(replace(window, start=absent_end))
    return tuple(result)


def _append_rework(order: Any, event: DisruptionEvent) -> Any:
    last = max(order.operations, key=lambda operation: operation.sequence)
    processing = event.rework_minutes or max(
        1,
        round(last.processing_minutes * event.rejected_quantity / max(1, order.quantity)),
    )
    operation_type = event.operation_type or last.operation_type
    rework = Operation(
        id=f"{order.id}-REWORK-{len(order.operations) + 1}",
        order_id=order.id,
        sequence=last.sequence + 1,
        operation_type=operation_type,
        processing_minutes=processing,
        required_skill=operation_type,
        eligible_machine_ids=last.eligible_machine_ids,
        predecessor_ids=(last.id,),
        setup_minutes=last.setup_minutes,
        quantity=event.rejected_quantity,
    )
    return replace(order, operations=(*order.operations, rework))


def _lost_production_cost(
    problem: PlanningProblem, event: DisruptionEvent
) -> float:
    if event.kind != DisruptionKind.MACHINE_BREAKDOWN or not event.machine_id or not event.end_at:
        return 0.0
    machine = problem.machine_map[event.machine_id]
    hours = max(0.0, (event.end_at - event.start_at).total_seconds() / 3600)
    dependent_revenue = sum(
        order.selling_price
        for order in problem.orders
        if any(machine.can_process(operation.operation_type) for operation in order.operations)
    )
    horizon_hours = max(
        1.0, (problem.horizon_end - problem.horizon_start).total_seconds() / 3600
    )
    return round(hours * (machine.hourly_cost + dependent_revenue / horizon_hours), 2)


def problem_default_completion(problem: PlanningProblem, order_id: str) -> datetime:
    return problem.horizon_end


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"cannot convert {value!r} to datetime")


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _datetime(value)
