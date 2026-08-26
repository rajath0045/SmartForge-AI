from __future__ import annotations

from datetime import timedelta

from app.optimizer import Operation, Order, ScheduleMode, SchedulingEngine
from app.services.capacity import calculate_machine_capacity, identify_bottleneck
from app.services.replanning import (
    DisruptionEvent,
    DisruptionKind,
    ReplanningService,
)
from app.services.rfq import OrderAcceptanceService, RFQDecision
from app.services.risk import analyze_risks, generate_recommendations
from app.services.simulation import simulate_delivery_confidence


def _rfq(problem, *, selling_price: float, material_cost: float) -> Order:
    operation = Operation(
        "RFQ-TURN",
        "RFQ-1",
        1,
        "TURNING",
        45,
        required_skill="TURNING",
        quantity=50,
    )
    return Order(
        "RFQ-1",
        "NEW-CUSTOMER",
        "TIER_2",
        "PF-A",
        50,
        problem.horizon_start + timedelta(days=1, hours=6),
        (operation,),
        release_at=problem.horizon_start,
        selling_price=selling_price,
        material_cost=material_cost,
        late_penalty_per_day=8_000,
        quality_reject_rate=0.02,
    )


def test_rfq_acceptance_is_capacity_and_profit_based(compact_problem):
    engine = SchedulingEngine(prefer_cp_sat=False)
    service = OrderAcceptanceService(engine)
    profitable = service.evaluate(
        compact_problem, _rfq(compact_problem, selling_price=80_000, material_cost=15_000)
    )
    loss_making = service.evaluate(
        compact_problem, _rfq(compact_problem, selling_price=100, material_cost=20_000)
    )

    assert profitable.decision in {
        RFQDecision.ACCEPT,
        RFQDecision.ACCEPT_WITH_OVERTIME,
        RFQDecision.ACCEPT_WITH_GENERATOR_USAGE,
    }
    assert profitable.delivery_confidence_pct > 50
    assert profitable.attractiveness.score > loss_making.attractiveness.score
    assert loss_making.decision == RFQDecision.REJECT
    assert any("incremental" in reason.lower() for reason in loss_making.reasons)


def test_breakdown_replan_freezes_history_and_avoids_outage(compact_problem):
    engine = SchedulingEngine(prefer_cp_sat=False)
    baseline = engine.generate(compact_problem, ScheduleMode.MOST_ON_TIME)
    event = DisruptionEvent(
        DisruptionKind.MACHINE_BREAKDOWN,
        compact_problem.horizon_start + timedelta(hours=3, minutes=30),
        compact_problem.horizon_start + timedelta(hours=7),
        machine_id="LATHE-1",
        description="spindle alarm",
    )
    result = ReplanningService(engine).replan(
        compact_problem, baseline, event, mode=ScheduleMode.MOST_ON_TIME
    )

    assert result.revised_schedule.valid
    assert result.frozen_task_ids
    for task in result.revised_schedule.tasks:
        if task.machine_id == "LATHE-1":
            assert task.end <= event.start_at or task.start >= event.end_at
    assert result.difference.cost_impact["total_disruption_cost"] >= 0
    assert result.difference.jobs_moved >= 0


def test_capacity_risk_and_recommendations_are_derived(compact_problem):
    schedule = SchedulingEngine(prefer_cp_sat=False).generate(
        compact_problem, ScheduleMode.MOST_ROBUST
    )
    capacity = calculate_machine_capacity(compact_problem, schedule)
    bottleneck = identify_bottleneck(compact_problem, schedule)
    risks = analyze_risks(compact_problem, schedule)
    recommendations = generate_recommendations(risks)

    assert len(capacity) == len(compact_problem.machines)
    assert bottleneck.machine_id in compact_problem.machine_map
    assert "finite-capacity" in bottleneck.explanation
    assert any(risk.category in {"MAINTENANCE", "LABOUR", "DELIVERY"} for risk in risks)
    assert all(item.net_benefit == round(item.expected_benefit - item.estimated_cost, 2) for item in recommendations)


def test_confidence_simulation_is_deterministic(compact_problem):
    schedule = SchedulingEngine(prefer_cp_sat=False).generate(
        compact_problem, ScheduleMode.MOST_ROBUST
    )
    first = simulate_delivery_confidence(
        compact_problem, schedule, iterations=80, seed=42
    )
    second = simulate_delivery_confidence(
        compact_problem, schedule, iterations=80, seed=42
    )
    assert first == second
    assert all(0 <= row.on_time_probability_pct <= 100 for row in first)

