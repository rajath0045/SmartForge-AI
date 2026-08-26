from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import timedelta

import pytest

from app.optimizer import (
    CalendarWindow,
    PowerWindow,
    ScheduleMode,
    ScheduleResult,
    ScheduleSolveStatus,
    ScheduleTask,
    SchedulingEngine,
    SolverKind,
    ViolationCode,
    validate_schedule,
)


def test_finite_schedule_respects_core_constraints(compact_problem):
    result = SchedulingEngine(prefer_cp_sat=False).generate(
        compact_problem, ScheduleMode.MOST_ON_TIME
    )

    assert result.feasible and result.valid
    assert result.solver == SolverKind.HEURISTIC
    assert {task.operation_id for task in result.tasks} == set(
        compact_problem.operation_map
    )

    tasks = {task.operation_id: task for task in result.tasks}
    assert tasks["O1-TURN"].start >= compact_problem.order_map["ORD-1"].release_at
    assert tasks["O1-GRIND"].start >= tasks["O1-TURN"].end
    assert tasks["O1-TURN"].machine_id.startswith("LATHE")
    assert tasks["O1-GRIND"].machine_id == "GRIND-1"
    assert tasks["O1-TURN"].operator_id == "OP-T"
    assert tasks["O1-GRIND"].operator_id == "OP-G"

    by_machine = defaultdict(list)
    for task in result.tasks:
        by_machine[task.machine_id].append(task)
    for machine_tasks in by_machine.values():
        ordered = sorted(machine_tasks, key=lambda task: task.start)
        assert all(right.start >= left.end for left, right in zip(ordered, ordered[1:]))


def test_sequence_dependent_changeover_is_capacity_not_decoration(compact_problem):
    result = SchedulingEngine(prefer_cp_sat=False).generate(
        compact_problem, ScheduleMode.CHEAPEST
    )
    lathe_tasks = sorted(
        (task for task in result.tasks if task.operation_type == "TURNING"),
        key=lambda task: task.start,
    )
    assert len(lathe_tasks) == 2
    if lathe_tasks[0].machine_id == lathe_tasks[1].machine_id:
        expected = 60 if lathe_tasks[0].part_family == "PF-A" else 90
        assert lathe_tasks[1].changeover_minutes == expected
        assert lathe_tasks[1].start >= lathe_tasks[0].end + timedelta(minutes=expected)


def test_most_robust_adds_enforced_machine_reserve(compact_problem):
    result = SchedulingEngine(prefer_cp_sat=False).generate(
        compact_problem, ScheduleMode.MOST_ROBUST
    )
    assert result.valid
    assert all(task.robust_buffer_minutes >= 5 for task in result.tasks)
    grinder = next(task for task in result.tasks if task.machine_id == "GRIND-1")
    assert grinder.robust_buffer_minutes > 0


def test_validator_detects_machine_and_operator_double_booking(compact_problem):
    start = compact_problem.horizon_start + timedelta(hours=1)
    tasks = [
        ScheduleTask(
            "T-1",
            "O1-TURN",
            "ORD-1",
            "LATHE-1",
            "OP-T",
            start,
            start + timedelta(hours=1),
            "SHIFT-1",
            "PF-A",
            "TURNING",
        ),
        ScheduleTask(
            "T-2",
            "O2-TURN",
            "ORD-2",
            "LATHE-1",
            "OP-T",
            start,
            start + timedelta(hours=1),
            "SHIFT-1",
            "PF-B",
            "TURNING",
        ),
    ]
    report = validate_schedule(compact_problem, tasks, require_complete=False)
    codes = {violation.code for violation in report.violations}
    assert ViolationCode.MACHINE_CONFLICT in codes
    assert ViolationCode.OPERATOR_CONFLICT in codes


def test_validator_rejects_capability_and_skill_mismatch(compact_problem):
    start = compact_problem.horizon_start + timedelta(hours=2)
    invalid = ScheduleTask(
        "BAD",
        "O1-GRIND",
        "ORD-1",
        "LATHE-1",
        "OP-T",
        start,
        start + timedelta(hours=1),
        "SHIFT-1",
        "PF-A",
        "GRINDING",
    )
    report = validate_schedule(compact_problem, [invalid], require_complete=False)
    codes = {violation.code for violation in report.violations}
    assert ViolationCode.MACHINE_CAPABILITY in codes
    assert ViolationCode.OPERATOR_SKILL in codes


def test_validator_rejects_maintenance_material_and_unpowered_work(compact_problem):
    start = compact_problem.horizon_start
    machine = replace(
        compact_problem.machine_map["LATHE-1"],
        unavailable=(
            CalendarWindow(start, start + timedelta(hours=2), "MAINTENANCE"),
        ),
    )
    problem = replace(
        compact_problem,
        machines=(
            machine,
            compact_problem.machine_map["LATHE-2"],
            compact_problem.machine_map["GRIND-1"],
        ),
        power_windows=(
            PowerWindow(
                start,
                start + timedelta(hours=3),
                grid_available=False,
                generator_available=False,
                name="OUTAGE",
            ),
        ),
    )
    invalid = ScheduleTask(
        "BLOCKED",
        "O1-TURN",
        "ORD-1",
        "LATHE-1",
        "OP-T",
        start,
        start + timedelta(hours=1),
        "SHIFT-1",
        "PF-A",
        "TURNING",
    )
    report = validate_schedule(problem, [invalid], require_complete=False)
    codes = {violation.code for violation in report.violations}
    assert ViolationCode.MACHINE_UNAVAILABLE in codes
    assert ViolationCode.MATERIAL_RELEASE in codes
    assert ViolationCode.POWER in codes


def test_validator_enforces_shared_generator_capacity(compact_problem):
    start = compact_problem.horizon_start + timedelta(hours=1)
    backup_operator = replace(
        compact_problem.operator_map["OP-G"],
        skills=frozenset({"TURNING"}),
        qualified_machine_types=frozenset({"LATHE"}),
    )
    problem = replace(
        compact_problem,
        operators=(compact_problem.operator_map["OP-T"], backup_operator),
        power_windows=(
            PowerWindow(
                compact_problem.horizon_start,
                compact_problem.horizon_start + timedelta(hours=8),
                grid_available=False,
                generator_available=True,
                generator_capacity_kw=15,
                name="LIMITED_GENERATOR",
            ),
        ),
    )
    tasks = [
        ScheduleTask(
            "GEN-1",
            "O1-TURN",
            "ORD-1",
            "LATHE-1",
            "OP-T",
            start,
            start + timedelta(hours=1),
            "SHIFT-1",
            "PF-A",
            "TURNING",
            uses_generator=True,
        ),
        ScheduleTask(
            "GEN-2",
            "O2-TURN",
            "ORD-2",
            "LATHE-2",
            "OP-G",
            start,
            start + timedelta(hours=1),
            "SHIFT-1",
            "PF-B",
            "TURNING",
            uses_generator=True,
        ),
    ]
    report = validate_schedule(problem, tasks, require_complete=False)
    assert ViolationCode.GENERATOR_CAPACITY in {
        violation.code for violation in report.violations
    }


def test_cp_sat_primary_engine_on_compact_problem(compact_problem):
    pytest.importorskip("ortools")
    result = SchedulingEngine(max_solve_seconds=3).generate(
        compact_problem, ScheduleMode.MOST_ON_TIME
    )
    assert result.solver == SolverKind.CP_SAT
    assert result.feasible and result.valid


def test_cp_sat_unknown_recovers_without_claiming_infeasible(compact_problem):
    class TimeLimitedEngine(SchedulingEngine):
        def _generate_cp_sat(self, problem, mode, cp_model):
            return ScheduleResult(
                mode=mode,
                status=ScheduleSolveStatus.INFEASIBLE,
                solver=SolverKind.CP_SAT,
                diagnostics=["CP-SAT returned UNKNOWN"],
            )

    result = TimeLimitedEngine().generate(compact_problem, ScheduleMode.MOST_ON_TIME)
    assert result.solver == SolverKind.HEURISTIC
    assert result.feasible and result.valid
    assert any("no incumbent" in message for message in result.diagnostics)
    assert not any("proven infeasible" in message for message in result.diagnostics)
