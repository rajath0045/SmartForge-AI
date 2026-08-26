"""Independent schedule validation.

Validation is intentionally separate from the solver.  A solver status alone is
not sufficient evidence that an API response is safe to present: this module
rechecks the manufacturing rules on concrete timestamps and resource IDs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Iterable

from .domain import PlanningProblem, ScheduleResult, ScheduleTask, changeover_for


class ViolationCode(StrEnum):
    MISSING_OPERATION = "MISSING_OPERATION"
    DUPLICATE_OPERATION = "DUPLICATE_OPERATION"
    UNKNOWN_RESOURCE = "UNKNOWN_RESOURCE"
    OUTSIDE_HORIZON = "OUTSIDE_HORIZON"
    INVALID_DURATION = "INVALID_DURATION"
    PRECEDENCE = "PRECEDENCE"
    MACHINE_CAPABILITY = "MACHINE_CAPABILITY"
    MACHINE_CONFLICT = "MACHINE_CONFLICT"
    MACHINE_UNAVAILABLE = "MACHINE_UNAVAILABLE"
    OPERATOR_SKILL = "OPERATOR_SKILL"
    OPERATOR_CONFLICT = "OPERATOR_CONFLICT"
    OPERATOR_OVERTIME = "OPERATOR_OVERTIME"
    MATERIAL_RELEASE = "MATERIAL_RELEASE"
    SHIFT = "SHIFT"
    POWER = "POWER"
    GENERATOR_CAPACITY = "GENERATOR_CAPACITY"
    CHANGEOVER = "CHANGEOVER"


@dataclass(frozen=True, slots=True)
class ScheduleViolation:
    code: ViolationCode
    message: str
    task_ids: tuple[str, ...] = ()
    resource_id: str | None = None


@dataclass(slots=True)
class ValidationReport:
    violations: list[ScheduleViolation] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.violations

    def by_code(self, code: ViolationCode | str) -> list[ScheduleViolation]:
        normalized = ViolationCode(str(getattr(code, "value", code)))
        return [violation for violation in self.violations if violation.code == normalized]


class ScheduleValidator:
    def validate(
        self,
        problem: PlanningProblem,
        schedule: ScheduleResult | Iterable[ScheduleTask],
        *,
        require_complete: bool = True,
    ) -> ValidationReport:
        tasks = list(schedule.tasks if isinstance(schedule, ScheduleResult) else schedule)
        report = ValidationReport()
        operation_map = problem.operation_map
        order_map = problem.order_map
        machine_map = problem.machine_map
        operator_map = problem.operator_map
        tasks_by_operation: dict[str, list[ScheduleTask]] = defaultdict(list)

        for task in tasks:
            tasks_by_operation[task.operation_id].append(task)
            operation = operation_map.get(task.operation_id)
            machine = machine_map.get(task.machine_id)
            operator = operator_map.get(task.operator_id)
            if operation is None:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.UNKNOWN_RESOURCE,
                        f"{task.id} references unknown operation {task.operation_id}",
                        (task.id,),
                    )
                )
                continue
            if machine is None or operator is None:
                missing = task.machine_id if machine is None else task.operator_id
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.UNKNOWN_RESOURCE,
                        f"{task.id} references unknown resource {missing}",
                        (task.id,),
                        missing,
                    )
                )
                continue
            if task.end <= task.start:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.INVALID_DURATION,
                        f"{task.id} must end after it starts",
                        (task.id,),
                    )
                )
            elif not task.is_frozen and task.duration_minutes != operation.duration_minutes:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.INVALID_DURATION,
                        f"{task.id} lasts {task.duration_minutes} min; operation requires {operation.duration_minutes}",
                        (task.id,),
                    )
                )
            if task.start < problem.horizon_start or task.end > problem.horizon_end:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.OUTSIDE_HORIZON,
                        f"{task.id} falls outside the planning horizon",
                        (task.id,),
                    )
                )
            if operation.eligible_machine_ids and task.machine_id not in operation.eligible_machine_ids:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.MACHINE_CAPABILITY,
                        f"{task.machine_id} is not eligible for {operation.id}",
                        (task.id,),
                        task.machine_id,
                    )
                )
            if not machine.can_process(operation.operation_type):
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.MACHINE_CAPABILITY,
                        f"{task.machine_id} cannot perform {operation.operation_type}",
                        (task.id,),
                        task.machine_id,
                    )
                )
            if not operator.is_qualified(machine, operation.skill):
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.OPERATOR_SKILL,
                        f"{task.operator_id} is not qualified for {operation.operation_type} on {task.machine_id}",
                        (task.id,),
                        task.operator_id,
                    )
                )
            order = order_map[operation.order_id]
            if order.release_at and task.start < order.release_at and not task.is_frozen:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.MATERIAL_RELEASE,
                        f"{task.id} starts before material release for {order.id}",
                        (task.id,),
                        order.id,
                    )
                )
            covering_shifts = [
                shift
                for shift in problem.shifts
                if shift.start <= task.start
                and shift.end
                >= task.end + timedelta(minutes=max(0, task.robust_buffer_minutes))
            ]
            if not covering_shifts:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.SHIFT,
                        f"{task.id} is not contained in one eligible shift window",
                        (task.id,),
                    )
                )
            elif not any(shift.name == task.shift_name for shift in covering_shifts):
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.SHIFT,
                        f"{task.id} is labelled {task.shift_name} but lies in a different shift",
                        (task.id,),
                    )
                )
            else:
                labelled = next(shift for shift in covering_shifts if shift.name == task.shift_name)
                if task.is_overtime != labelled.is_overtime:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.SHIFT,
                            f"{task.id} overtime flag does not match {labelled.name}",
                            (task.id,),
                        )
                    )
            if operator.availability and not any(
                window.start <= task.start and window.end >= task.end
                for window in operator.availability
            ):
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.SHIFT,
                        f"{task.operator_id} is unavailable during {task.id}",
                        (task.id,),
                        task.operator_id,
                    )
                )
            for unavailable in machine.unavailable:
                if _overlap(task.start, task.end, unavailable.start, unavailable.end):
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.MACHINE_UNAVAILABLE,
                            f"{task.id} overlaps {unavailable.name} on {machine.id}",
                            (task.id,),
                            machine.id,
                        )
                    )
            self._validate_power(problem, task, machine.power_kw, report)

        if require_complete:
            for operation_id in operation_map:
                count = len(tasks_by_operation.get(operation_id, ()))
                if count == 0:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.MISSING_OPERATION,
                            f"operation {operation_id} is not scheduled",
                            resource_id=operation_id,
                        )
                    )
                elif count > 1:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.DUPLICATE_OPERATION,
                            f"operation {operation_id} is scheduled {count} times",
                            tuple(task.id for task in tasks_by_operation[operation_id]),
                            operation_id,
                        )
                    )

        self._validate_precedence(problem, tasks_by_operation, report)
        self._validate_resources(problem, tasks, report)
        self._validate_generator_capacity(problem, tasks, report)
        return report

    def _validate_precedence(
        self,
        problem: PlanningProblem,
        tasks_by_operation: dict[str, list[ScheduleTask]],
        report: ValidationReport,
    ) -> None:
        for operation in problem.operation_map.values():
            successor_tasks = tasks_by_operation.get(operation.id, ())
            if not successor_tasks:
                continue
            successor = min(successor_tasks, key=lambda task: task.start)
            for predecessor_id in operation.predecessor_ids:
                predecessor_tasks = tasks_by_operation.get(predecessor_id, ())
                if not predecessor_tasks:
                    continue
                predecessor = max(predecessor_tasks, key=lambda task: task.end)
                if successor.start < predecessor.end:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.PRECEDENCE,
                            f"{successor.id} starts before predecessor {predecessor.id} finishes",
                            (predecessor.id, successor.id),
                            operation.id,
                        )
                    )

    def _validate_resources(
        self,
        problem: PlanningProblem,
        tasks: list[ScheduleTask],
        report: ValidationReport,
    ) -> None:
        by_machine: dict[str, list[ScheduleTask]] = defaultdict(list)
        by_operator: dict[str, list[ScheduleTask]] = defaultdict(list)
        for task in tasks:
            if task.machine_id in problem.machine_map:
                by_machine[task.machine_id].append(task)
            if task.operator_id in problem.operator_map:
                by_operator[task.operator_id].append(task)

        for machine_id, machine_tasks in by_machine.items():
            machine = problem.machine_map[machine_id]
            ordered = sorted(machine_tasks, key=lambda task: (task.start, task.id))
            for previous, current in zip(ordered, ordered[1:]):
                previous_occupied_end = previous.end + timedelta(
                    minutes=max(0, previous.robust_buffer_minutes)
                )
                if current.start < previous_occupied_end:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.MACHINE_CONFLICT,
                            f"{previous.id} and {current.id} overlap on {machine_id}",
                            (previous.id, current.id),
                            machine_id,
                        )
                    )
                    continue
                setup_minutes, _ = changeover_for(
                    problem, machine, previous.part_family, current.part_family
                )
                if current.start < previous_occupied_end + timedelta(minutes=setup_minutes):
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.CHANGEOVER,
                            f"{current.id} needs {setup_minutes} changeover minutes after {previous.id}",
                            (previous.id, current.id),
                            machine_id,
                        )
                    )
                if not current.is_frozen and current.changeover_minutes != setup_minutes:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.CHANGEOVER,
                            f"{current.id} reports {current.changeover_minutes} changeover minutes; expected {setup_minutes}",
                            (current.id,),
                            machine_id,
                        )
                    )

        for operator_id, operator_tasks in by_operator.items():
            ordered = sorted(operator_tasks, key=lambda task: (task.start, task.id))
            for previous, current in zip(ordered, ordered[1:]):
                if current.start < previous.end:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.OPERATOR_CONFLICT,
                            f"{previous.id} and {current.id} overlap for operator {operator_id}",
                            (previous.id, current.id),
                            operator_id,
                        )
                    )
            operator = problem.operator_map[operator_id]
            if operator.max_overtime_minutes is not None:
                overtime = sum(task.duration_minutes for task in ordered if task.is_overtime)
                if overtime > operator.max_overtime_minutes:
                    report.violations.append(
                        ScheduleViolation(
                            ViolationCode.OPERATOR_OVERTIME,
                            f"{operator_id} has {overtime} overtime minutes; limit is {operator.max_overtime_minutes}",
                            tuple(task.id for task in ordered if task.is_overtime),
                            operator_id,
                        )
                    )

    def _validate_power(
        self,
        problem: PlanningProblem,
        task: ScheduleTask,
        demand_kw: float,
        report: ValidationReport,
    ) -> None:
        events = [
            event
            for event in problem.power_windows
            if _overlap(task.start, task.end, event.start, event.end)
        ]
        boundaries = {task.start, task.end}
        for event in events:
            boundaries.add(max(task.start, event.start))
            boundaries.add(min(task.end, event.end))
        ordered = sorted(boundaries)
        used_generator = False
        for left, right in zip(ordered, ordered[1:]):
            active = [event for event in events if event.start <= left and event.end >= right]
            event = active[-1] if active else None
            if event is None or event.grid_available:
                continue
            used_generator = True
            if (
                not task.uses_generator
                or not event.generator_available
                or event.generator_capacity_kw + 1e-9 < demand_kw
            ):
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.POWER,
                        f"{task.id} runs without adequate grid/generator power",
                        (task.id,),
                        task.machine_id,
                    )
                )
        if task.uses_generator and not used_generator:
            report.violations.append(
                ScheduleViolation(
                    ViolationCode.POWER,
                    f"{task.id} is marked for generator use outside an outage",
                    (task.id,),
                    task.machine_id,
                )
            )

    def _validate_generator_capacity(
        self,
        problem: PlanningProblem,
        tasks: list[ScheduleTask],
        report: ValidationReport,
    ) -> None:
        generator_tasks = [task for task in tasks if task.uses_generator]
        moments = sorted({moment for task in generator_tasks for moment in (task.start, task.end)})
        for start, end in zip(moments, moments[1:]):
            if end <= start:
                continue
            active = [task for task in generator_tasks if task.start < end and task.end > start]
            if not active:
                continue
            demand = sum(problem.machine_map[task.machine_id].power_kw for task in active)
            events = [
                event
                for event in problem.power_windows
                if not event.grid_available and event.start <= start and event.end >= end
            ]
            capacity = min((event.generator_capacity_kw for event in events), default=0.0)
            if demand > capacity + 1e-9:
                report.violations.append(
                    ScheduleViolation(
                        ViolationCode.GENERATOR_CAPACITY,
                        f"generator demand {demand:.1f} kW exceeds {capacity:.1f} kW capacity",
                        tuple(task.id for task in active),
                    )
                )


def validate_schedule(
    problem: PlanningProblem,
    schedule: ScheduleResult | Iterable[ScheduleTask],
    *,
    require_complete: bool = True,
) -> ValidationReport:
    return ScheduleValidator().validate(problem, schedule, require_complete=require_complete)


def _overlap(
    left_start: datetime,
    left_end: datetime,
    right_start: datetime,
    right_end: datetime,
) -> bool:
    return left_start < right_end and left_end > right_start
