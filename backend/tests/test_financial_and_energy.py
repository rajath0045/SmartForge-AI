from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from app.optimizer import ScheduleTask
from app.services.energy import evaluate_generator_decision
from app.services.financial import (
    calculate_schedule_financials,
    penalty_for_lateness,
)


def test_financial_calculator_accounts_for_costs_and_continuous_penalty(compact_problem):
    order = compact_problem.order_map["ORD-2"]
    completion = order.due_at + timedelta(hours=12)
    task = ScheduleTask(
        "FIN",
        "O2-TURN",
        "ORD-2",
        "LATHE-1",
        "OP-T",
        completion - timedelta(hours=1),
        completion,
        "SHIFT-1",
        "PF-B",
        "TURNING",
    )
    summary = calculate_schedule_financials(compact_problem, [task])
    row = summary.by_order["ORD-2"]

    assert penalty_for_lateness(order, completion) == 4_500.0
    assert row.regular_labour_cost == 280.0
    assert row.machine_cost == 80.0
    assert row.grid_energy_cost == 90.0
    assert row.late_penalty == 4_500.0
    assert summary.expected_profit == round(summary.revenue - summary.total_cost, 2)


def test_overtime_and_generator_are_separate_cost_buckets(compact_problem):
    order = compact_problem.order_map["ORD-2"]
    start = compact_problem.horizon_start + timedelta(hours=8)
    task = ScheduleTask(
        "OT-GEN",
        "O2-TURN",
        order.id,
        "LATHE-1",
        "OP-T",
        start,
        start + timedelta(hours=1),
        "SHIFT-OT",
        "PF-B",
        "TURNING",
        is_overtime=True,
        uses_generator=True,
    )
    summary = calculate_schedule_financials(compact_problem, [task])
    row = summary.by_order[order.id]
    assert row.regular_labour_cost == 0
    assert row.overtime_cost == 420.0
    assert row.grid_energy_cost == 0
    assert row.generator_cost == 280.0


def test_incomplete_route_is_not_reported_as_delivered_or_recognized_revenue(
    compact_problem,
):
    order = compact_problem.order_map["ORD-1"]
    start = compact_problem.horizon_start
    first_operation_only = ScheduleTask(
        "PARTIAL",
        "O1-TURN",
        order.id,
        "LATHE-1",
        "OP-T",
        start,
        start + timedelta(hours=1),
        "SHIFT-1",
        "PF-A",
        "TURNING",
    )

    summary = calculate_schedule_financials(compact_problem, [first_operation_only])

    assert summary.by_order[order.id].completion_at is None
    assert summary.by_order[order.id].revenue == 0
    assert summary.on_time_delivery_pct == 0
    assert summary.late_orders == len(compact_problem.orders)


def test_generator_economics_runs_only_when_avoided_value_exceeds_cost(compact_problem):
    expensive_penalty_order = replace(
        compact_problem.order_map["ORD-1"], late_penalty_per_day=120_000
    )
    problem = compact_problem.with_orders(
        (expensive_penalty_order, compact_problem.order_map["ORD-2"])
    )
    run = evaluate_generator_decision(
        problem,
        machine_id="GRIND-1",
        runtime_minutes=120,
        affected_order_ids=["ORD-1"],
        avoided_delay_minutes=240,
    )
    skip = evaluate_generator_decision(
        compact_problem,
        machine_id="GRIND-1",
        runtime_minutes=120,
        affected_order_ids=["ORD-2"],
        avoided_delay_minutes=15,
    )
    assert run.should_run and run.net_benefit > 0
    assert not skip.should_run and skip.net_benefit < 0
    assert "exceeds" in run.explanation
