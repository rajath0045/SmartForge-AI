from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.optimizer import (
    CalendarWindow,
    ChangeoverRule,
    CostConfig,
    Machine,
    Operation,
    Operator,
    Order,
    PlanningProblem,
)


@pytest.fixture()
def compact_problem() -> PlanningProblem:
    start = datetime(2026, 9, 7, 6, 0)  # Monday
    shifts = (
        CalendarWindow(start, start + timedelta(hours=8), "SHIFT-1"),
        CalendarWindow(
            start + timedelta(hours=8),
            start + timedelta(hours=12),
            "SHIFT-OT",
            is_overtime=True,
        ),
        CalendarWindow(
            start + timedelta(days=1),
            start + timedelta(days=1, hours=8),
            "SHIFT-1",
        ),
    )
    machines = (
        Machine(
            "LATHE-1",
            "LATHE",
            frozenset({"TURNING"}),
            power_kw=10,
            hourly_cost=80,
            health_score=86,
            failure_probability=0.08,
        ),
        Machine(
            "LATHE-2",
            "LATHE",
            frozenset({"TURNING"}),
            power_kw=8,
            hourly_cost=130,
            health_score=96,
            failure_probability=0.02,
        ),
        Machine(
            "GRIND-1",
            "GRINDER",
            frozenset({"GRINDING"}),
            power_kw=16,
            hourly_cost=220,
            health_score=72,
            failure_probability=0.20,
        ),
    )
    operators = (
        Operator(
            "OP-T",
            frozenset({"TURNING"}),
            qualified_machine_types=frozenset({"LATHE"}),
            availability=shifts,
            max_overtime_minutes=240,
        ),
        Operator(
            "OP-G",
            frozenset({"GRINDING"}),
            qualified_machine_types=frozenset({"GRINDER"}),
            availability=shifts,
            max_overtime_minutes=240,
        ),
    )
    turn_1 = Operation(
        "O1-TURN",
        "ORD-1",
        1,
        "TURNING",
        60,
        required_skill="TURNING",
        quantity=100,
    )
    grind_1 = Operation(
        "O1-GRIND",
        "ORD-1",
        2,
        "GRINDING",
        60,
        required_skill="GRINDING",
        predecessor_ids=(turn_1.id,),
        quantity=100,
    )
    turn_2 = Operation(
        "O2-TURN",
        "ORD-2",
        1,
        "TURNING",
        60,
        required_skill="TURNING",
        quantity=80,
    )
    orders = (
        Order(
            "ORD-1",
            "C-T1",
            "TIER_1",
            "PF-A",
            100,
            start + timedelta(hours=7),
            (turn_1, grind_1),
            release_at=start + timedelta(hours=1),
            selling_price=180_000,
            material_cost=60_000,
            late_penalty_per_day=48_000,
            strategic_weight=1.8,
            quality_reject_rate=0.03,
        ),
        Order(
            "ORD-2",
            "C-T2",
            "TIER_2",
            "PF-B",
            80,
            start + timedelta(hours=7, minutes=30),
            (turn_2,),
            release_at=start,
            selling_price=90_000,
            material_cost=28_000,
            late_penalty_per_day=9_000,
            quality_reject_rate=0.02,
        ),
    )
    return PlanningProblem(
        start,
        start + timedelta(days=2),
        machines,
        operators,
        orders,
        shifts,
        changeovers=(
            ChangeoverRule("PF-A", "PF-B", 60, 500),
            ChangeoverRule("PF-B", "PF-A", 90, 700),
        ),
        costs=CostConfig(
            regular_labour_per_hour=280,
            overtime_multiplier=1.5,
            grid_cost_per_kwh=9,
            generator_cost_per_kwh=28,
            changeover_labour_per_hour=300,
            rework_cost_per_unit=100,
            robust_buffer_ratio=0.15,
        ),
    )

