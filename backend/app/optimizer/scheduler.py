"""Deterministic finite-capacity production scheduler.

Google OR-Tools CP-SAT is the primary engine.  The model uses optional
machine/operator/shift alternatives, exact disjunctive resource constraints,
and a circuit per machine for sequence-dependent changeovers.  A deterministic
serial-schedule-generation heuristic is used only when OR-Tools is not
installed (or is explicitly disabled by a caller such as a constrained demo).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from math import ceil
from typing import Any, Iterable

from .domain import (
    CalendarWindow,
    Machine,
    Operation,
    Operator,
    Order,
    PlanningProblem,
    PowerWindow,
    ScheduleMode,
    ScheduleResult,
    ScheduleSolveStatus,
    ScheduleTask,
    SolverKind,
    at_minute,
    changeover_for,
    minute_offset,
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    operation_id: str
    machine_id: str
    operator_id: str
    window_start: int
    window_end: int
    shift_name: str
    is_overtime: bool
    is_sunday: bool
    uses_generator: bool
    power_key: tuple[int, int, int] | None
    processing_minutes: int
    buffer_minutes: int
    assignment_cost: float


@dataclass(frozen=True, slots=True)
class _Busy:
    start: datetime
    end: datetime
    family: str | None = None
    task: ScheduleTask | None = None


@dataclass(frozen=True, slots=True)
class _GeneratorBusy:
    start: datetime
    end: datetime
    demand_kw: float


class SchedulingEngine:
    """Generate a validated two-week finite-capacity schedule.

    Parameters are deterministic by default: one CP-SAT worker and a fixed
    random seed.  `prefer_cp_sat=False` exists for explicit environments where
    native solver binaries are not permitted; production callers should leave
    it enabled.
    """

    def __init__(
        self,
        *,
        max_solve_seconds: float = 12.0,
        random_seed: int = 202503,
        prefer_cp_sat: bool = True,
    ) -> None:
        self.max_solve_seconds = max(0.1, float(max_solve_seconds))
        self.random_seed = int(random_seed)
        self.prefer_cp_sat = bool(prefer_cp_sat)

    def generate(
        self,
        problem: PlanningProblem,
        mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
    ) -> ScheduleResult:
        mode = _schedule_mode(mode)
        errors = self._input_errors(problem)
        if errors:
            return ScheduleResult(
                mode=mode,
                status=ScheduleSolveStatus.INVALID_INPUT,
                solver=SolverKind.HEURISTIC,
                diagnostics=errors,
                generated_at=problem.horizon_start,
            )

        cp_model: Any | None = None
        if self.prefer_cp_sat:
            try:
                from ortools.sat.python import cp_model as imported_cp_model

                cp_model = imported_cp_model
            except (ImportError, ModuleNotFoundError, OSError):
                cp_model = None

        if cp_model is not None:
            result = self._generate_cp_sat(problem, mode, cp_model)
            # UNKNOWN means the time-limited search found no incumbent; it is
            # not a proof of infeasibility.  The assessment brief explicitly
            # permits a defensible heuristic when exact optimization becomes
            # expensive, so return a validated finite-capacity schedule while
            # preserving the solver diagnostic.
            if (
                result.status == ScheduleSolveStatus.INFEASIBLE
                and any("UNKNOWN" in diagnostic for diagnostic in result.diagnostics)
            ):
                cp_diagnostics = list(result.diagnostics)
                result = self._generate_heuristic(problem, mode)
                result.diagnostics[:0] = [
                    *cp_diagnostics,
                    "CP-SAT time limit produced no incumbent; deterministic heuristic recovery applied",
                ]
        else:
            reason = (
                "OR-Tools unavailable; used deterministic finite-capacity heuristic fallback"
                if self.prefer_cp_sat
                else "CP-SAT explicitly disabled; used deterministic finite-capacity heuristic"
            )
            result = self._generate_heuristic(problem, mode)
            result.diagnostics.insert(0, reason)

        return self._finalize(problem, result)

    def _generate_cp_sat(
        self,
        problem: PlanningProblem,
        mode: ScheduleMode,
        cp_model: Any,
    ) -> ScheduleResult:
        model = cp_model.CpModel()
        horizon = minute_offset(problem.horizon_end, problem.horizon_start)
        orders = problem.order_map
        frozen_by_operation = {task.operation_id: task for task in problem.fixed_tasks}
        operations = [
            operation
            for order in problem.orders
            for operation in order.operations
            if operation.id not in frozen_by_operation
        ]

        start_vars: dict[str, Any] = {}
        end_vars: dict[str, Any] = {}
        candidates: dict[str, list[_Candidate]] = {}
        presence: dict[tuple[str, int], Any] = {}
        machine_intervals: dict[str, list[Any]] = defaultdict(list)
        operator_intervals: dict[str, list[Any]] = defaultdict(list)
        generator_intervals: dict[tuple[int, int, int], list[tuple[Any, int]]] = defaultdict(list)
        on_machine: dict[tuple[str, str], Any] = {}
        objective_terms: list[Any] = []
        objective_scale = max(1, problem.costs.objective_scale)

        for operation in operations:
            start = model.NewIntVar(0, horizon, f"start_{operation.id}")
            end = model.NewIntVar(0, horizon, f"end_{operation.id}")
            model.Add(end == start + operation.duration_minutes)
            start_vars[operation.id] = start
            end_vars[operation.id] = end
            order = orders[operation.order_id]
            planning_release = problem.metadata.get("planning_release_at")
            release = max(
                problem.horizon_start,
                order.release_at or problem.horizon_start,
                planning_release
                if isinstance(planning_release, datetime)
                else problem.horizon_start,
            )
            model.Add(start >= max(0, minute_offset(release, problem.horizon_start)))

            operation_candidates = self._candidates(problem, operation, order, mode)
            candidates[operation.id] = operation_candidates
            literals: list[Any] = []
            by_machine: dict[str, list[Any]] = defaultdict(list)
            for index, candidate in enumerate(operation_candidates):
                literal = model.NewBoolVar(f"use_{operation.id}_{index}")
                presence[(operation.id, index)] = literal
                literals.append(literal)
                by_machine[candidate.machine_id].append(literal)
                occupied_end = model.NewIntVar(0, horizon, f"occupied_end_{operation.id}_{index}")
                machine_interval = model.NewOptionalIntervalVar(
                    start,
                    candidate.processing_minutes + candidate.buffer_minutes,
                    occupied_end,
                    literal,
                    f"machine_interval_{operation.id}_{index}",
                )
                operator_interval = model.NewOptionalIntervalVar(
                    start,
                    candidate.processing_minutes,
                    end,
                    literal,
                    f"operator_interval_{operation.id}_{index}",
                )
                model.Add(start >= candidate.window_start).OnlyEnforceIf(literal)
                model.Add(occupied_end <= candidate.window_end).OnlyEnforceIf(literal)
                machine_intervals[candidate.machine_id].append(machine_interval)
                operator_intervals[candidate.operator_id].append(operator_interval)
                if candidate.power_key is not None:
                    generator_intervals[candidate.power_key].append(
                        (machine_interval, max(1, round(problem.machine_map[candidate.machine_id].power_kw * 10)))
                    )
                assignment_coefficient = self._assignment_objective_coefficient(
                    problem, order, candidate, mode, objective_scale
                )
                if assignment_coefficient:
                    objective_terms.append(literal * assignment_coefficient)
            if not literals:
                return ScheduleResult(
                    mode=mode,
                    status=ScheduleSolveStatus.INFEASIBLE,
                    solver=SolverKind.CP_SAT,
                    diagnostics=[
                        f"{operation.id} has no compatible machine/operator/shift/power alternative"
                    ],
                    generated_at=problem.horizon_start,
                )
            model.AddExactlyOne(literals)
            for machine in problem.machines:
                machine_literals = by_machine.get(machine.id, [])
                if machine_literals:
                    assigned = model.NewBoolVar(f"on_{operation.id}_{machine.id}")
                    model.Add(assigned == sum(machine_literals))
                    on_machine[(operation.id, machine.id)] = assigned

        # Fixed work and machine downtime are genuine resource intervals.
        fixed_start: dict[str, Any] = {}
        fixed_end: dict[str, Any] = {}
        for task in problem.fixed_tasks:
            machine_end = task.end + timedelta(
                minutes=max(0, task.robust_buffer_minutes)
            )
            machine_clip = _clip_to_horizon(task.start, machine_end, problem)
            operator_clip = _clip_to_horizon(task.start, task.end, problem)
            if machine_clip is None:
                continue
            start_minute, machine_end_minute = machine_clip
            interval = model.NewIntervalVar(
                start_minute,
                machine_end_minute - start_minute,
                machine_end_minute,
                f"fixed_machine_{task.id}",
            )
            machine_intervals[task.machine_id].append(interval)
            if task.operator_id in problem.operator_map and operator_clip is not None:
                operator_start, operator_end = operator_clip
                operator_intervals[task.operator_id].append(
                    model.NewIntervalVar(
                        operator_start,
                        operator_end - operator_start,
                        operator_end,
                        f"fixed_operator_{task.id}",
                    )
                )
            key = f"FIXED::{task.id}"
            fixed_start[key] = model.NewConstant(start_minute)
            fixed_end[key] = model.NewConstant(machine_end_minute)

        for machine in problem.machines:
            for index, window in enumerate(machine.unavailable):
                clipped = _clip_to_horizon(window.start, window.end, problem)
                if clipped is None:
                    continue
                start_minute, end_minute = clipped
                machine_intervals[machine.id].append(
                    model.NewIntervalVar(
                        start_minute,
                        end_minute - start_minute,
                        end_minute,
                        f"unavailable_{machine.id}_{index}",
                    )
                )
        for machine_id, intervals in machine_intervals.items():
            if intervals:
                model.AddNoOverlap(intervals)
        for operator_id, intervals in operator_intervals.items():
            if intervals:
                model.AddNoOverlap(intervals)

        for operator in problem.operators:
            if operator.max_overtime_minutes is None:
                continue
            overtime_terms: list[Any] = []
            for operation_id, operation_candidates in candidates.items():
                for index, candidate in enumerate(operation_candidates):
                    if candidate.operator_id == operator.id and candidate.is_overtime:
                        overtime_terms.append(presence[(operation_id, index)] * candidate.processing_minutes)
            if overtime_terms:
                model.Add(sum(overtime_terms) <= operator.max_overtime_minutes)

        for (window_start, window_end, capacity), intervals in generator_intervals.items():
            if intervals:
                model.AddCumulative(
                    [interval for interval, _ in intervals],
                    [demand for _, demand in intervals],
                    capacity,
                )

        # Route precedence, including a predecessor frozen by replanning.
        for operation in operations:
            for predecessor_id in operation.predecessor_ids:
                if predecessor_id in end_vars:
                    model.Add(start_vars[operation.id] >= end_vars[predecessor_id])
                elif predecessor_id in frozen_by_operation:
                    release = minute_offset(
                        frozen_by_operation[predecessor_id].end, problem.horizon_start
                    )
                    model.Add(start_vars[operation.id] >= max(0, release))

        changeover_arcs: list[tuple[Any, int, float]] = []
        # AddCircuit makes the setup relationship exact: setup is charged only
        # between adjacent operations in the selected sequence on each machine.
        for machine in problem.machines:
            pending_ids = sorted(
                operation.id for operation in operations if (operation.id, machine.id) in on_machine
            )
            fixed_tasks = sorted(
                (task for task in problem.fixed_tasks if task.machine_id == machine.id),
                key=lambda task: (task.start, task.id),
            )
            if not pending_ids and not fixed_tasks:
                continue
            node_keys = pending_ids + [f"FIXED::{task.id}" for task in fixed_tasks]
            fixed_lookup = {f"FIXED::{task.id}": task for task in fixed_tasks}
            arcs: list[tuple[int, int, Any]] = []
            empty = model.NewBoolVar(f"empty_{machine.id}")
            arcs.append((0, 0, empty))
            presences: dict[str, Any] = {}
            for key in node_keys:
                if key.startswith("FIXED::"):
                    presences[key] = model.NewConstant(1)
                else:
                    presences[key] = on_machine[(key, machine.id)]
                node = node_keys.index(key) + 1
                arcs.append((node, node, presences[key].Not()))
                model.AddImplication(presences[key], empty.Not())
                model.AddImplication(empty, presences[key].Not())
                first = model.NewBoolVar(f"arc_0_{node}_{machine.id}")
                last = model.NewBoolVar(f"arc_{node}_0_{machine.id}")
                model.AddImplication(first, presences[key])
                model.AddImplication(last, presences[key])
                arcs.extend(((0, node, first), (node, 0, last)))

            for left_index, left_key in enumerate(node_keys, start=1):
                for right_index, right_key in enumerate(node_keys, start=1):
                    if left_key == right_key:
                        continue
                    arc = model.NewBoolVar(
                        f"arc_{left_index}_{right_index}_{machine.id}"
                    )
                    model.AddImplication(arc, presences[left_key])
                    model.AddImplication(arc, presences[right_key])
                    arcs.append((left_index, right_index, arc))
                    left_family = (
                        fixed_lookup[left_key].part_family
                        if left_key.startswith("FIXED::")
                        else orders[problem.operation_map[left_key].order_id].part_family
                    )
                    right_family = (
                        fixed_lookup[right_key].part_family
                        if right_key.startswith("FIXED::")
                        else orders[problem.operation_map[right_key].order_id].part_family
                    )
                    setup_minutes, setup_cost = changeover_for(
                        problem, machine, left_family, right_family
                    )
                    left_end = fixed_end[left_key] if left_key.startswith("FIXED::") else end_vars[left_key]
                    right_start = (
                        fixed_start[right_key]
                        if right_key.startswith("FIXED::")
                        else start_vars[right_key]
                    )
                    buffer_minutes = (
                        0
                        if left_key.startswith("FIXED::")
                        else self._robust_buffer(
                            problem,
                            orders[problem.operation_map[left_key].order_id],
                            problem.operation_map[left_key],
                            machine,
                            mode,
                        )
                    )
                    model.Add(
                        right_start >= left_end + buffer_minutes + setup_minutes
                    ).OnlyEnforceIf(arc)
                    changeover_arcs.append((arc, setup_minutes, setup_cost))
            model.AddCircuit(arcs)

        # Completion and lateness are explicitly represented, not inferred from
        # a display metric, so each objective has enforceable due-date behavior.
        for order in problem.orders:
            completion_sources: list[Any] = []
            for operation in order.operations:
                if operation.id in end_vars:
                    completion_sources.append(end_vars[operation.id])
                elif operation.id in frozen_by_operation:
                    completion_sources.append(
                        model.NewConstant(
                            max(
                                0,
                                minute_offset(
                                    frozen_by_operation[operation.id].end,
                                    problem.horizon_start,
                                ),
                            )
                        )
                    )
            if not completion_sources:
                continue
            completion = model.NewIntVar(0, max(horizon * 2, 1), f"completion_{order.id}")
            model.AddMaxEquality(completion, completion_sources)
            due = minute_offset(order.due_at, problem.horizon_start)
            lateness = model.NewIntVar(0, max(horizon * 2, 1), f"lateness_{order.id}")
            model.Add(lateness >= completion - due)
            model.Add(lateness >= 0)
            coefficient = self._lateness_coefficient(order, mode, objective_scale)
            if coefficient:
                objective_terms.append(lateness * coefficient)

        changeover_weight = {
            ScheduleMode.CHEAPEST: 1.0,
            ScheduleMode.MOST_ON_TIME: 0.20,
            ScheduleMode.MOST_ROBUST: 0.60,
        }[mode]
        for arc, minutes, explicit_cost in changeover_arcs:
            monetary_cost = explicit_cost + (
                minutes / 60 * problem.costs.changeover_labour_per_hour
            )
            coefficient = max(
                1 if minutes else 0,
                round(monetary_cost * objective_scale * changeover_weight),
            )
            if coefficient:
                objective_terms.append(arc * coefficient)
        model.Minimize(sum(objective_terms) if objective_terms else 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.max_solve_seconds
        solver.parameters.random_seed = self.random_seed
        solver.parameters.num_search_workers = 1
        solver.parameters.cp_model_presolve = True
        status = solver.Solve(model)
        status_name = solver.StatusName(status).upper()
        if status_name not in {"OPTIMAL", "FEASIBLE"}:
            return ScheduleResult(
                mode=mode,
                status=ScheduleSolveStatus.INFEASIBLE,
                solver=SolverKind.CP_SAT,
                diagnostics=[f"CP-SAT returned {status_name}"],
                generated_at=problem.horizon_start,
            )

        tasks = list(problem.fixed_tasks)
        for operation in operations:
            selected_index = next(
                index
                for index in range(len(candidates[operation.id]))
                if solver.BooleanValue(presence[(operation.id, index)])
            )
            candidate = candidates[operation.id][selected_index]
            order = orders[operation.order_id]
            start = at_minute(problem.horizon_start, solver.Value(start_vars[operation.id]))
            end = at_minute(problem.horizon_start, solver.Value(end_vars[operation.id]))
            tasks.append(
                ScheduleTask(
                    id=f"TASK-{operation.id}",
                    operation_id=operation.id,
                    order_id=operation.order_id,
                    machine_id=candidate.machine_id,
                    operator_id=candidate.operator_id,
                    start=start,
                    end=end,
                    shift_name=candidate.shift_name,
                    part_family=order.part_family,
                    operation_type=operation.operation_type,
                    quantity=operation.quantity or order.quantity,
                    is_overtime=candidate.is_overtime,
                    is_sunday=candidate.is_sunday,
                    uses_generator=candidate.uses_generator,
                    robust_buffer_minutes=candidate.buffer_minutes,
                )
            )
        tasks = self._annotate_changeovers(problem, tasks)
        return ScheduleResult(
            mode=mode,
            status=(
                ScheduleSolveStatus.OPTIMAL
                if status_name == "OPTIMAL"
                else ScheduleSolveStatus.FEASIBLE
            ),
            solver=SolverKind.CP_SAT,
            tasks=sorted(tasks, key=lambda task: (task.start, task.machine_id, task.id)),
            objective_value=solver.ObjectiveValue() / objective_scale,
            diagnostics=[
                f"CP-SAT {status_name.lower()} in {solver.WallTime():.3f}s",
                "Sequence-dependent changeovers modeled with per-machine circuits",
            ],
            generated_at=problem.horizon_start,
        )

    def _generate_heuristic(
        self, problem: PlanningProblem, mode: ScheduleMode
    ) -> ScheduleResult:
        frozen_by_operation = {task.operation_id: task for task in problem.fixed_tasks}
        operations = {
            operation.id: operation
            for order in problem.orders
            for operation in order.operations
            if operation.id not in frozen_by_operation
        }
        orders = problem.order_map
        candidate_cache = {
            operation.id: self._candidates(
                problem, operation, orders[operation.order_id], mode
            )
            for operation in operations.values()
        }
        machine_busy: dict[str, list[_Busy]] = defaultdict(list)
        operator_busy: dict[str, list[_Busy]] = defaultdict(list)
        generator_busy: list[_GeneratorBusy] = []
        for machine in problem.machines:
            machine_busy[machine.id].extend(
                _Busy(window.start, window.end) for window in machine.unavailable
            )
        for task in problem.fixed_tasks:
            machine_busy[task.machine_id].append(
                _Busy(
                    task.start,
                    task.end
                    + timedelta(minutes=max(0, task.robust_buffer_minutes)),
                    task.part_family,
                    task,
                )
            )
            operator_busy[task.operator_id].append(
                _Busy(task.start, task.end, task.part_family, task)
            )

        completed = set(frozen_by_operation)
        tasks = list(problem.fixed_tasks)
        unscheduled: set[str] = set()
        diagnostics: list[str] = [
            "Heuristic uses deterministic precedence-ready dispatch with finite machine/operator calendars"
        ]
        while len(completed) + len(unscheduled) < len(operations) + len(frozen_by_operation):
            ready = [
                operation
                for operation in operations.values()
                if operation.id not in completed
                and operation.id not in unscheduled
                and all(
                    predecessor in completed or predecessor not in operations
                    for predecessor in operation.predecessor_ids
                )
            ]
            if not ready:
                remaining = sorted(set(operations) - completed - unscheduled)
                diagnostics.append(f"No precedence-ready operation among: {', '.join(remaining)}")
                unscheduled.update(remaining)
                break

            ready.sort(key=lambda operation: self._dispatch_key(problem, operation, mode, tasks))
            chosen_operation: Operation | None = None
            chosen_task: ScheduleTask | None = None
            # A serial schedule-generation scheme commits the highest-ranked
            # feasible ready operation. This avoids repeatedly rescoring every
            # RFQ/order against thousands of shift alternatives.
            for operation in ready:
                order = orders[operation.order_id]
                predecessor_end = max(
                    [
                        next(
                            task.end
                            for task in tasks
                            if task.operation_id == predecessor_id
                        )
                        for predecessor_id in operation.predecessor_ids
                        if any(task.operation_id == predecessor_id for task in tasks)
                    ]
                    or [problem.horizon_start]
                )
                ready_at = max(
                    problem.horizon_start,
                    order.release_at or problem.horizon_start,
                    problem.metadata.get("planning_release_at")
                    if isinstance(problem.metadata.get("planning_release_at"), datetime)
                    else problem.horizon_start,
                    predecessor_end,
                )
                allocation = self._best_heuristic_allocation(
                    problem,
                    operation,
                    order,
                    mode,
                    ready_at,
                    machine_busy,
                    operator_busy,
                    generator_busy,
                    candidate_cache[operation.id],
                )
                if allocation is None:
                    continue
                task, _score = allocation
                chosen_operation = operation
                chosen_task = task
                break
            if chosen_operation is None or chosen_task is None:
                blocked = ready[0]
                unscheduled.add(blocked.id)
                diagnostics.append(
                    f"{blocked.id} could not fit any compatible qualified resource window"
                )
                continue
            tasks.append(chosen_task)
            completed.add(chosen_operation.id)
            busy = _Busy(
                chosen_task.start,
                chosen_task.end + timedelta(minutes=chosen_task.robust_buffer_minutes),
                chosen_task.part_family,
                chosen_task,
            )
            machine_busy[chosen_task.machine_id].append(busy)
            operator_busy[chosen_task.operator_id].append(
                _Busy(chosen_task.start, chosen_task.end, chosen_task.part_family, chosen_task)
            )
            if chosen_task.uses_generator:
                generator_busy.append(
                    _GeneratorBusy(
                        chosen_task.start,
                        chosen_task.end,
                        problem.machine_map[chosen_task.machine_id].power_kw,
                    )
                )

        tasks = self._annotate_changeovers(problem, tasks)
        status = (
            ScheduleSolveStatus.FEASIBLE
            if not unscheduled
            else ScheduleSolveStatus.INFEASIBLE
        )
        if unscheduled:
            diagnostics.append(f"Unscheduled operations: {', '.join(sorted(unscheduled))}")
        return ScheduleResult(
            mode=mode,
            status=status,
            solver=SolverKind.HEURISTIC,
            tasks=sorted(tasks, key=lambda task: (task.start, task.machine_id, task.id)),
            diagnostics=diagnostics,
            generated_at=problem.horizon_start,
        )

    def _best_heuristic_allocation(
        self,
        problem: PlanningProblem,
        operation: Operation,
        order: Order,
        mode: ScheduleMode,
        ready_at: datetime,
        machine_busy: dict[str, list[_Busy]],
        operator_busy: dict[str, list[_Busy]],
        generator_busy: list[_GeneratorBusy],
        operation_candidates: list[_Candidate],
    ) -> tuple[ScheduleTask, tuple[Any, ...]] | None:
        best: tuple[ScheduleTask, tuple[Any, ...]] | None = None
        sorted_machine_busy = {
            machine_id: sorted(entries, key=lambda item: item.start)
            for machine_id, entries in machine_busy.items()
        }
        sorted_operator_busy = {
            operator_id: sorted(entries, key=lambda item: item.start)
            for operator_id, entries in operator_busy.items()
        }
        for candidate in operation_candidates:
            machine = problem.machine_map[candidate.machine_id]
            window_start = at_minute(problem.horizon_start, candidate.window_start)
            window_end = at_minute(problem.horizon_start, candidate.window_end)
            cursor = max(window_start, ready_at)
            occupied_duration = timedelta(
                minutes=candidate.processing_minutes + candidate.buffer_minutes
            )
            machine_entries = sorted_machine_busy.get(candidate.machine_id, [])
            operator_entries = sorted_operator_busy.get(candidate.operator_id, [])
            production_entries = [entry for entry in machine_entries if entry.family]
            for _ in range(
                len(machine_entries) + len(operator_entries) + len(generator_busy) + 3
            ):
                previous = max(
                    (entry for entry in production_entries if entry.end <= cursor),
                    key=lambda entry: entry.end,
                    default=None,
                )
                setup_minutes = 0
                setup_cost = 0.0
                if previous is not None and previous.family:
                    setup_minutes, setup_cost = changeover_for(
                        problem, machine, previous.family, order.part_family
                    )
                    setup_ready_at = previous.end + timedelta(minutes=setup_minutes)
                    if setup_ready_at > cursor:
                        cursor = setup_ready_at
                        # Advancing for a setup can jump over another task that
                        # was inserted into this machine's timeline earlier in
                        # the serial search.  Re-evaluate adjacency before
                        # accepting the slot so the changeover is based on the
                        # task that is truly immediately before this one.
                        continue
                end = cursor + timedelta(minutes=candidate.processing_minutes)
                occupied_end = cursor + occupied_duration
                conflict = _first_overlap(
                    cursor,
                    occupied_end,
                    [*machine_entries, *operator_entries],
                )
                if conflict is not None:
                    cursor = conflict.end
                    continue
                if candidate.uses_generator and candidate.power_key is not None:
                    generator_conflict_end = _generator_conflict_end(
                        cursor,
                        end,
                        machine.power_kw,
                        candidate.power_key[2] / 10,
                        generator_busy,
                    )
                    if generator_conflict_end is not None:
                        cursor = generator_conflict_end
                        continue
                # Recompute the following production task after setup/conflict
                # movement.  Using the pre-movement neighbour can miss a task
                # that was inserted earlier, under-reserving its changeover.
                following = min(
                    (
                        entry
                        for entry in production_entries
                        if entry.start >= occupied_end
                    ),
                    key=lambda entry: entry.start,
                    default=None,
                )
                if following is not None:
                    next_setup, _ = changeover_for(
                        problem, machine, order.part_family, following.family
                    )
                    if occupied_end + timedelta(minutes=next_setup) > following.start:
                        cursor = following.end
                        continue
                if occupied_end > window_end:
                    break
                lateness_minutes = max(0, round((end - order.due_at).total_seconds() / 60))
                risk_cost = (
                    candidate.processing_minutes
                    * (machine.failure_probability + max(0.0, 100 - machine.health_score) / 100)
                )
                if mode == ScheduleMode.CHEAPEST:
                    score = (
                        candidate.assignment_cost
                        + setup_cost
                        + setup_minutes / 60 * problem.costs.changeover_labour_per_hour
                        + lateness_minutes / 1440 * order.late_penalty_per_day,
                        end,
                        candidate.machine_id,
                        candidate.operator_id,
                    )
                elif mode == ScheduleMode.MOST_ON_TIME:
                    score = (
                        lateness_minutes * _tier_weight(order.customer_tier),
                        end,
                        candidate.assignment_cost,
                        candidate.machine_id,
                    )
                else:
                    score = (
                        lateness_minutes * _tier_weight(order.customer_tier),
                        risk_cost,
                        candidate.assignment_cost,
                        end,
                        candidate.machine_id,
                    )
                task = ScheduleTask(
                    id=f"TASK-{operation.id}",
                    operation_id=operation.id,
                    order_id=operation.order_id,
                    machine_id=candidate.machine_id,
                    operator_id=candidate.operator_id,
                    start=cursor,
                    end=end,
                    shift_name=candidate.shift_name,
                    part_family=order.part_family,
                    operation_type=operation.operation_type,
                    quantity=operation.quantity or order.quantity,
                    is_overtime=candidate.is_overtime,
                    is_sunday=candidate.is_sunday,
                    uses_generator=candidate.uses_generator,
                    changeover_minutes=setup_minutes,
                    changeover_cost=setup_cost,
                    robust_buffer_minutes=candidate.buffer_minutes,
                )
                if best is None or score < best[1]:
                    best = task, score
                break
        return best

    def _candidates(
        self,
        problem: PlanningProblem,
        operation: Operation,
        order: Order,
        mode: ScheduleMode,
    ) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        for machine in sorted(problem.machines, key=lambda item: item.id):
            if operation.eligible_machine_ids and machine.id not in operation.eligible_machine_ids:
                continue
            if not machine.can_process(operation.operation_type):
                continue
            if str(machine.status).upper() == "BREAKDOWN" and not machine.unavailable:
                continue
            buffer_minutes = self._robust_buffer(problem, order, operation, machine, mode)
            for operator in sorted(problem.operators, key=lambda item: item.id):
                if not operator.is_qualified(machine, operation.skill):
                    continue
                for shift in sorted(problem.shifts, key=lambda item: (item.start, item.name)):
                    if shift.end <= problem.horizon_start or shift.start >= problem.horizon_end:
                        continue
                    if shift.is_overtime and (
                        not problem.allow_overtime or not operator.overtime_eligible
                    ):
                        continue
                    operator_windows = operator.availability or (shift,)
                    for availability in operator_windows:
                        overlap = _intersection(shift.start, shift.end, availability.start, availability.end)
                        if overlap is None:
                            continue
                        start, end = overlap
                        for power_segment in self._power_segments(problem, start, end, machine):
                            segment_start, segment_end, uses_generator, power_key, energy_rate = power_segment
                            required = operation.duration_minutes + buffer_minutes
                            if (segment_end - segment_start).total_seconds() / 60 < required:
                                continue
                            hours = operation.duration_minutes / 60
                            labour_rate = problem.costs.regular_labour_per_hour
                            if shift.is_overtime:
                                labour_rate *= problem.costs.overtime_multiplier
                            if shift.is_sunday:
                                labour_rate *= problem.costs.sunday_multiplier
                            assignment_cost = hours * (
                                machine.hourly_cost + labour_rate + machine.power_kw * energy_rate
                            )
                            start_offset = max(
                                0, minute_offset(segment_start, problem.horizon_start)
                            )
                            end_offset = min(
                                minute_offset(problem.horizon_end, problem.horizon_start),
                                int((segment_end - problem.horizon_start).total_seconds() // 60),
                            )
                            candidates.append(
                                _Candidate(
                                    operation_id=operation.id,
                                    machine_id=machine.id,
                                    operator_id=operator.id,
                                    window_start=start_offset,
                                    window_end=end_offset,
                                    shift_name=shift.name,
                                    is_overtime=shift.is_overtime,
                                    is_sunday=shift.is_sunday,
                                    uses_generator=uses_generator,
                                    power_key=power_key,
                                    processing_minutes=operation.duration_minutes,
                                    buffer_minutes=buffer_minutes,
                                    assignment_cost=assignment_cost,
                                )
                            )
        return candidates

    def _power_segments(
        self,
        problem: PlanningProblem,
        start: datetime,
        end: datetime,
        machine: Machine,
    ) -> list[tuple[datetime, datetime, bool, tuple[int, int, int] | None, float]]:
        events = [
            event
            for event in problem.power_windows
            if event.start < end and event.end > start
        ]
        boundaries = {start, end}
        for event in events:
            boundaries.add(max(start, event.start))
            boundaries.add(min(end, event.end))
        ordered = sorted(boundaries)
        segments: list[tuple[datetime, datetime, bool, tuple[int, int, int] | None, float]] = []
        for left, right in zip(ordered, ordered[1:]):
            if right <= left:
                continue
            active = [event for event in events if event.start <= left and event.end >= right]
            event = active[-1] if active else None
            if event is None or event.grid_available:
                rate = (
                    event.grid_cost_per_kwh
                    if event and event.grid_cost_per_kwh is not None
                    else problem.costs.grid_cost_per_kwh
                )
                segments.append((left, right, False, None, rate))
                continue
            generator_usable = (
                problem.allow_generator
                and event.generator_available
                and event.generator_capacity_kw + 1e-9 >= machine.power_kw
            )
            if not generator_usable:
                continue
            capacity = max(1, round(event.generator_capacity_kw * 10))
            key = (
                minute_offset(left, problem.horizon_start),
                minute_offset(right, problem.horizon_start),
                capacity,
            )
            rate = event.generator_cost_per_kwh or problem.costs.generator_cost_per_kwh
            segments.append((left, right, True, key, rate))
        return segments

    def _robust_buffer(
        self,
        problem: PlanningProblem,
        order: Order,
        operation: Operation,
        machine: Machine,
        mode: ScheduleMode,
    ) -> int:
        if mode != ScheduleMode.MOST_ROBUST:
            return 0
        tier_factor = 1.25 if _tier_weight(order.customer_tier) >= 5 else 1.0
        risk_ratio = (
            problem.costs.robust_buffer_ratio
            + machine.failure_probability * 0.5
            + max(0.0, 75.0 - machine.health_score) / 500.0
        )
        return max(5, ceil(operation.duration_minutes * risk_ratio * tier_factor))

    def _assignment_objective_coefficient(
        self,
        problem: PlanningProblem,
        order: Order,
        candidate: _Candidate,
        mode: ScheduleMode,
        scale: int,
    ) -> int:
        cost_weight = {
            ScheduleMode.CHEAPEST: 1.0,
            ScheduleMode.MOST_ON_TIME: 0.12,
            ScheduleMode.MOST_ROBUST: 0.55,
        }[mode]
        value = candidate.assignment_cost * cost_weight
        if mode == ScheduleMode.MOST_ROBUST:
            machine = problem.machine_map[candidate.machine_id]
            value += candidate.processing_minutes * (
                machine.failure_probability * 25
                + max(0.0, 80 - machine.health_score) * 0.15
            )
        return max(0, round(value * scale))

    def _lateness_coefficient(
        self, order: Order, mode: ScheduleMode, scale: int
    ) -> int:
        direct_penalty_per_minute = order.late_penalty_per_day / 1440
        if mode == ScheduleMode.CHEAPEST:
            rupees_per_minute = direct_penalty_per_minute
        elif mode == ScheduleMode.MOST_ON_TIME:
            rupees_per_minute = (
                direct_penalty_per_minute
                + 35 * _tier_weight(order.customer_tier) * max(1.0, order.strategic_weight)
            )
        else:
            rupees_per_minute = (
                direct_penalty_per_minute
                + 15 * _tier_weight(order.customer_tier) * max(1.0, order.strategic_weight)
            )
        return max(1, round(rupees_per_minute * scale))

    def _dispatch_key(
        self,
        problem: PlanningProblem,
        operation: Operation,
        mode: ScheduleMode,
        tasks: Iterable[ScheduleTask],
    ) -> tuple[Any, ...]:
        order = problem.order_map[operation.order_id]
        if mode == ScheduleMode.CHEAPEST:
            return (
                order.due_at,
                -order.late_penalty_per_day,
                operation.duration_minutes,
                operation.id,
            )
        if mode == ScheduleMode.MOST_ON_TIME:
            return (
                -_tier_weight(order.customer_tier) * max(1.0, order.strategic_weight),
                order.due_at,
                -order.late_penalty_per_day,
                operation.duration_minutes,
                operation.id,
            )
        eligible_risk = [
            machine.failure_probability
            for machine in problem.machines
            if machine.can_process(operation.operation_type)
        ]
        risk = min(eligible_risk, default=1.0)
        return (
            -_tier_weight(order.customer_tier) * max(1.0, order.strategic_weight),
            order.due_at,
            risk,
            operation.duration_minutes,
            operation.id,
        )

    def _annotate_changeovers(
        self, problem: PlanningProblem, tasks: list[ScheduleTask]
    ) -> list[ScheduleTask]:
        machine_map = problem.machine_map
        result: list[ScheduleTask] = []
        by_machine: dict[str, list[ScheduleTask]] = defaultdict(list)
        for task in tasks:
            by_machine[task.machine_id].append(task)
        for machine_id, machine_tasks in by_machine.items():
            previous: ScheduleTask | None = None
            for task in sorted(machine_tasks, key=lambda item: (item.start, item.id)):
                if task.is_frozen and task.changeover_minutes:
                    annotated = task
                elif previous is None:
                    annotated = replace(task, changeover_minutes=0, changeover_cost=0.0)
                else:
                    minutes, cost = changeover_for(
                        problem,
                        machine_map[machine_id],
                        previous.part_family,
                        task.part_family,
                    )
                    annotated = replace(
                        task, changeover_minutes=minutes, changeover_cost=cost
                    )
                result.append(annotated)
                previous = annotated
        return result

    def _input_errors(self, problem: PlanningProblem) -> list[str]:
        errors: list[str] = []
        operation_ids = [
            operation.id for order in problem.orders for operation in order.operations
        ]
        if len(operation_ids) != len(set(operation_ids)):
            errors.append("operation ids must be globally unique")
        machine_ids = [machine.id for machine in problem.machines]
        if len(machine_ids) != len(set(machine_ids)):
            errors.append("machine ids must be unique")
        operator_ids = [operator.id for operator in problem.operators]
        if len(operator_ids) != len(set(operator_ids)):
            errors.append("operator ids must be unique")
        known = set(operation_ids)
        graph: dict[str, tuple[str, ...]] = {}
        for order in problem.orders:
            for operation in order.operations:
                unknown = set(operation.predecessor_ids) - known
                if unknown:
                    errors.append(
                        f"{operation.id} references unknown predecessors {sorted(unknown)}"
                    )
                graph[operation.id] = operation.predecessor_ids
                if order.release_at and order.release_at > problem.horizon_end:
                    errors.append(f"{order.id} material releases after the planning horizon")
        if _has_cycle(graph):
            errors.append("operation precedence graph contains a cycle")
        return errors

    def _finalize(
        self, problem: PlanningProblem, result: ScheduleResult
    ) -> ScheduleResult:
        if not result.tasks:
            return result
        from .validator import ScheduleValidator

        report = ScheduleValidator().validate(problem, result.tasks, require_complete=result.feasible)
        result.valid = report.valid and result.feasible
        result.violations = report.violations
        if report.violations:
            result.diagnostics.extend(violation.message for violation in report.violations)
        from app.services.financial import calculate_schedule_financials

        result.metrics = calculate_schedule_financials(problem, result.tasks).as_dict()
        result.metrics.update(
            {
                "mode": str(getattr(result.mode, "value", result.mode)),
                "solver": result.solver.value,
                "is_valid": result.valid,
                "scheduled_operations": len(
                    {task.operation_id for task in result.tasks}
                ),
            }
        )
        return result


def _schedule_mode(mode: ScheduleMode | str) -> ScheduleMode:
    if isinstance(mode, ScheduleMode):
        return mode
    return ScheduleMode(str(getattr(mode, "value", mode)).upper())


def _tier_weight(tier: str) -> int:
    normalized = str(getattr(tier, "value", tier)).upper().replace("-", "_")
    return {"TIER_1": 8, "TIER1": 8, "TIER_2": 3, "TIER2": 3}.get(normalized, 1)


def _intersection(
    left_start: datetime,
    left_end: datetime,
    right_start: datetime,
    right_end: datetime,
) -> tuple[datetime, datetime] | None:
    start = max(left_start, right_start)
    end = min(left_end, right_end)
    return (start, end) if end > start else None


def _clip_to_horizon(
    start: datetime, end: datetime, problem: PlanningProblem
) -> tuple[int, int] | None:
    overlap = _intersection(start, end, problem.horizon_start, problem.horizon_end)
    if overlap is None:
        return None
    return (
        max(0, minute_offset(overlap[0], problem.horizon_start)),
        min(
            minute_offset(problem.horizon_end, problem.horizon_start),
            int((overlap[1] - problem.horizon_start).total_seconds() // 60),
        ),
    )


def _first_overlap(
    start: datetime, end: datetime, entries: Iterable[_Busy]
) -> _Busy | None:
    overlapping = [entry for entry in entries if start < entry.end and end > entry.start]
    return min(overlapping, key=lambda entry: (entry.end, entry.start)) if overlapping else None


def _adjacent_busy(
    entries: list[_Busy], moment: datetime
) -> tuple[_Busy | None, _Busy | None]:
    previous = max(
        (entry for entry in entries if entry.end <= moment),
        key=lambda entry: entry.end,
        default=None,
    )
    following = min(
        (entry for entry in entries if entry.start >= moment),
        key=lambda entry: entry.start,
        default=None,
    )
    return previous, following


def _generator_conflict_end(
    start: datetime,
    end: datetime,
    demand_kw: float,
    capacity_kw: float,
    entries: list[_GeneratorBusy],
) -> datetime | None:
    """Return an existing task end when adding demand would overload diesel."""

    overlapping = [entry for entry in entries if start < entry.end and end > entry.start]
    if demand_kw > capacity_kw + 1e-9:
        return end
    boundaries = sorted(
        {start, end}
        | {
            moment
            for entry in overlapping
            for moment in (max(start, entry.start), min(end, entry.end))
        }
    )
    for left, right in zip(boundaries, boundaries[1:]):
        active = [entry for entry in overlapping if entry.start < right and entry.end > left]
        if demand_kw + sum(entry.demand_kw for entry in active) > capacity_kw + 1e-9:
            return min(entry.end for entry in active)
    return None


def _has_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for predecessor in graph.get(node, ()):
            if predecessor in graph and visit(predecessor):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)
