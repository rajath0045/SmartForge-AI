from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import (
    ChangeoverMatrix,
    CostConfiguration,
    Machine,
    Operator,
    PowerEvent,
    ProductionOrder,
    Shift,
)
from app.optimizer import ScheduleMode, SchedulingEngine, problem_from_records


def test_seeded_orm_records_adapt_to_valid_finite_schedule():
    with SessionLocal() as db:
        rows = lambda model: list(db.scalars(select(model)).unique())
        machines = rows(Machine)
        if not machines:
            pytest.skip("demo database is not seeded")
        problem = problem_from_records(
            horizon_start=datetime(2026, 9, 1, 6),
            horizon_end=datetime(2026, 9, 15, 6),
            machines=machines,
            operators=rows(Operator),
            orders=rows(ProductionOrder),
            shifts=rows(Shift),
            power_windows=rows(PowerEvent),
            changeovers=rows(ChangeoverMatrix),
            costs=rows(CostConfiguration),
        )

    assert (len(problem.machines), len(problem.operators), len(problem.orders)) == (
        14,
        40,
        25,
    )
    assert len(problem.operation_map) == 96
    assert problem.costs.generator_cost_per_kwh == 28.5
    assert all(operator.availability for operator in problem.operators)
    assert all(order.release_at is not None for order in problem.orders)
    assert problem.changeovers[0].minutes > 0

    for mode in ScheduleMode:
        result = SchedulingEngine(prefer_cp_sat=False).generate(problem, mode)
        assert result.feasible and result.valid, (
            mode,
            [violation.message for violation in result.violations],
        )
        assert len(result.tasks) == 96
