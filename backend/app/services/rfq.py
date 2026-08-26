"""Capable-to-promise and risk-adjusted RFQ acceptance."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.optimizer.domain import Order, PlanningProblem, ScheduleMode, ScheduleResult
from app.optimizer.scheduler import SchedulingEngine

from .capacity import calculate_machine_capacity
from .financial import FinancialSummary, calculate_schedule_financials


class RFQDecision(StrEnum):
    ACCEPT = "ACCEPT"
    ACCEPT_WITH_OVERTIME = "ACCEPT WITH OVERTIME"
    ACCEPT_WITH_GENERATOR_USAGE = "ACCEPT WITH GENERATOR USAGE"
    ACCEPT_WITH_NEGOTIATED_DELIVERY_DATE = "ACCEPT WITH NEGOTIATED DELIVERY DATE"
    ACCEPT_WITH_PARTIAL_DELIVERY = "ACCEPT WITH PARTIAL DELIVERY"
    OUTSOURCE_BOTTLENECK_OPERATION = "OUTSOURCE BOTTLENECK OPERATION"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class AttractivenessScore:
    score: float
    expected_contribution_margin: float
    expected_late_penalty: float
    overtime_cost: float
    generator_cost: float
    changeover_cost: float
    reliability_risk_cost: float
    strategic_value: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class RFQEvaluation:
    order_id: str
    decision: RFQDecision
    delivery_confidence_pct: float
    requested_delivery_at: datetime
    recommended_promise_at: datetime | None
    estimated_revenue: float
    expected_production_cost: float
    overtime_cost: float
    expected_penalty_exposure: float
    generator_cost: float
    expected_contribution_margin: float
    displacement_penalty_on_committed_orders: float
    attractiveness: AttractivenessScore
    reasons: list[str]
    constraints: list[str]
    schedule: ScheduleResult | None = None
    partial_delivery_pct: float | None = None

    def as_dict(self, *, include_schedule: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "order_id": self.order_id,
            "decision": self.decision.value,
            "delivery_confidence_pct": self.delivery_confidence_pct,
            "requested_delivery_at": self.requested_delivery_at.isoformat(),
            "recommended_promise_at": self.recommended_promise_at.isoformat()
            if self.recommended_promise_at
            else None,
            "estimated_revenue": self.estimated_revenue,
            "expected_production_cost": self.expected_production_cost,
            "overtime_cost": self.overtime_cost,
            "expected_penalty_exposure": self.expected_penalty_exposure,
            "generator_cost": self.generator_cost,
            "expected_contribution_margin": self.expected_contribution_margin,
            "displacement_penalty_on_committed_orders": self.displacement_penalty_on_committed_orders,
            "attractiveness": self.attractiveness.as_dict(),
            "reasons": self.reasons,
            "constraints": self.constraints,
            "partial_delivery_pct": self.partial_delivery_pct,
        }
        if include_schedule:
            data["schedule"] = self.schedule
        return data


class OrderAcceptanceService:
    def __init__(self, engine: SchedulingEngine | None = None) -> None:
        self.engine = engine or SchedulingEngine()

    def evaluate(
        self,
        problem: PlanningProblem,
        proposed_order: Order,
        *,
        baseline_schedule: ScheduleResult | None = None,
        mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
    ) -> RFQEvaluation:
        if proposed_order.id in problem.order_map:
            raise ValueError(f"order id {proposed_order.id} already exists")
        proposed_order = _normalize_operation_order_ids(proposed_order)
        mode = ScheduleMode(str(getattr(mode, "value", mode)).upper())
        baseline = baseline_schedule or self.engine.generate(problem, mode)
        baseline_financial = calculate_schedule_financials(problem, baseline.tasks)
        trial_problem = problem.with_orders((*problem.orders, proposed_order))
        trial = self.engine.generate(trial_problem, mode)
        constraints = _hard_constraint_notes(trial_problem, proposed_order)

        if not trial.feasible or not trial.valid:
            return self._infeasible_evaluation(
                problem,
                trial_problem,
                proposed_order,
                baseline_financial,
                trial,
                constraints,
            )

        trial_financial = calculate_schedule_financials(trial_problem, trial.tasks)
        new_financial = trial_financial.by_order[proposed_order.id]
        new_tasks = [task for task in trial.tasks if task.order_id == proposed_order.id]
        completion = max((task.end for task in new_tasks), default=None)
        displacement = _committed_penalty_increase(
            problem, baseline_financial, trial_financial
        )
        incremental_profit = trial_financial.expected_profit - baseline_financial.expected_profit
        confidence = _delivery_confidence(trial_problem, proposed_order, new_tasks, completion)
        attractiveness = _attractiveness(
            proposed_order,
            new_financial,
            confidence,
            displacement,
        )
        reasons: list[str] = []
        reasons.append(
            f"Incremental expected contribution after production risk is ₹{incremental_profit:,.0f}."
        )
        if displacement > 0:
            reasons.append(
                f"Insertion adds ₹{displacement:,.0f} of penalty exposure to committed orders."
            )

        if displacement > max(0.0, new_financial.expected_profit) or incremental_profit < 0:
            decision = RFQDecision.REJECT
            reasons.append(
                "The proposed margin does not cover the incremental factory cost and committed-order penalty exposure."
            )
        elif completion and completion > proposed_order.due_at:
            decision = RFQDecision.ACCEPT_WITH_NEGOTIATED_DELIVERY_DATE
            reasons.append(
                f"The earliest validated completion is {completion.isoformat()}, after the requested promise."
            )
        elif any(task.uses_generator for task in new_tasks):
            decision = RFQDecision.ACCEPT_WITH_GENERATOR_USAGE
            reasons.append(
                f"Generator dispatch costs ₹{new_financial.generator_cost:,.0f} and is included in the positive margin."
            )
        elif any(task.is_overtime for task in new_tasks):
            decision = RFQDecision.ACCEPT_WITH_OVERTIME
            reasons.append(
                f"Qualified overtime costs ₹{new_financial.overtime_cost:,.0f} and preserves the requested date."
            )
        else:
            decision = RFQDecision.ACCEPT
            reasons.append("All operations fit regular finite capacity before the requested delivery date.")

        production_cost = (
            new_financial.material_cost
            + new_financial.regular_labour_cost
            + new_financial.overtime_cost
            + new_financial.machine_cost
            + new_financial.grid_energy_cost
            + new_financial.generator_cost
            + new_financial.changeover_cost
            + new_financial.expected_rework_cost
        )
        return RFQEvaluation(
            order_id=proposed_order.id,
            decision=decision,
            delivery_confidence_pct=confidence,
            requested_delivery_at=proposed_order.due_at,
            recommended_promise_at=completion,
            estimated_revenue=round(proposed_order.selling_price, 2),
            expected_production_cost=round(production_cost, 2),
            overtime_cost=new_financial.overtime_cost,
            expected_penalty_exposure=round(
                new_financial.late_penalty + displacement, 2
            ),
            generator_cost=new_financial.generator_cost,
            expected_contribution_margin=round(incremental_profit, 2),
            displacement_penalty_on_committed_orders=round(displacement, 2),
            attractiveness=attractiveness,
            reasons=reasons,
            constraints=constraints,
            schedule=trial,
        )

    def _infeasible_evaluation(
        self,
        base_problem: PlanningProblem,
        trial_problem: PlanningProblem,
        proposed_order: Order,
        baseline_financial: FinancialSummary,
        trial: ScheduleResult,
        constraints: list[str],
    ) -> RFQEvaluation:
        capability_gaps = _capability_gaps(trial_problem, proposed_order)
        required_minutes = sum(operation.duration_minutes for operation in proposed_order.operations)
        estimated_outsource = required_minutes / 60 * trial_problem.costs.outsourcing_cost_per_hour
        gross_contribution = proposed_order.selling_price - proposed_order.material_cost
        capacity = calculate_machine_capacity(base_problem, trial.tasks or ())
        available = sum(item.remaining_minutes for item in capacity)
        partial_fraction = min(1.0, available / max(1, required_minutes))
        reasons = [
            "No complete schedule satisfies all machine, labour, calendar, material, and power constraints within the horizon."
        ]
        reasons.extend(trial.diagnostics[-3:])
        if capability_gaps and gross_contribution > estimated_outsource:
            decision = RFQDecision.OUTSOURCE_BOTTLENECK_OPERATION
            reasons.append(
                f"Outsourcing the unsupported bottleneck is estimated at ₹{estimated_outsource:,.0f}, below gross contribution ₹{gross_contribution:,.0f}."
            )
            partial_pct = None
        elif 0.25 <= partial_fraction < 1 and gross_contribution * partial_fraction > 0:
            decision = RFQDecision.ACCEPT_WITH_PARTIAL_DELIVERY
            partial_pct = round(partial_fraction * 100, 1)
            reasons.append(
                f"Approximately {partial_pct:.1f}% can be covered by remaining modeled capacity; promise the balance separately."
            )
        else:
            decision = RFQDecision.REJECT
            partial_pct = None
            reasons.append("Available capacity and recovery options do not support a defensible promise.")
        confidence = max(5.0, round(partial_fraction * 60, 1))
        risk_cost = gross_contribution * (1 - confidence / 100)
        raw = gross_contribution - estimated_outsource - risk_cost
        attractiveness = AttractivenessScore(
            score=round(max(0.0, min(100.0, 50 + 50 * raw / max(1, proposed_order.selling_price))), 1),
            expected_contribution_margin=round(gross_contribution, 2),
            expected_late_penalty=0.0,
            overtime_cost=0.0,
            generator_cost=0.0,
            changeover_cost=0.0,
            reliability_risk_cost=round(risk_cost, 2),
            strategic_value=round(
                min(proposed_order.selling_price * 0.15, proposed_order.strategic_weight * 10_000),
                2,
            ),
        )
        return RFQEvaluation(
            order_id=proposed_order.id,
            decision=decision,
            delivery_confidence_pct=confidence,
            requested_delivery_at=proposed_order.due_at,
            recommended_promise_at=trial_problem.horizon_end,
            estimated_revenue=round(proposed_order.selling_price, 2),
            expected_production_cost=round(proposed_order.material_cost + estimated_outsource, 2),
            overtime_cost=0.0,
            expected_penalty_exposure=0.0,
            generator_cost=0.0,
            expected_contribution_margin=round(raw, 2),
            displacement_penalty_on_committed_orders=0.0,
            attractiveness=attractiveness,
            reasons=reasons,
            constraints=[*constraints, *capability_gaps],
            schedule=trial,
            partial_delivery_pct=partial_pct,
        )


def evaluate_rfq(
    problem: PlanningProblem,
    proposed_order: Order,
    *,
    baseline_schedule: ScheduleResult | None = None,
    mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
    engine: SchedulingEngine | None = None,
) -> RFQEvaluation:
    return OrderAcceptanceService(engine).evaluate(
        problem,
        proposed_order,
        baseline_schedule=baseline_schedule,
        mode=mode,
    )


def _normalize_operation_order_ids(order: Order) -> Order:
    if all(operation.order_id == order.id for operation in order.operations):
        return order
    return replace(
        order,
        operations=tuple(
            replace(operation, order_id=order.id) for operation in order.operations
        ),
    )


def _committed_penalty_increase(
    problem: PlanningProblem,
    baseline: FinancialSummary,
    trial: FinancialSummary,
) -> float:
    return sum(
        max(
            0.0,
            trial.by_order[order.id].late_penalty
            - baseline.by_order[order.id].late_penalty,
        )
        for order in problem.orders
        if order.id in trial.by_order and order.id in baseline.by_order
    )


def _delivery_confidence(
    problem: PlanningProblem,
    order: Order,
    tasks: list[Any],
    completion: datetime | None,
) -> float:
    if completion is None:
        return 5.0
    slack_hours = (order.due_at - completion).total_seconds() / 3600
    machines = [problem.machine_map[task.machine_id] for task in tasks]
    average_failure = (
        sum(machine.failure_probability for machine in machines) / len(machines)
        if machines
        else 0.5
    )
    redundancy_penalty = 0.0
    for task in tasks:
        operation = problem.operation_map.get(task.operation_id)
        machine = problem.machine_map[task.machine_id]
        if operation and sum(
            operator.is_qualified(machine, operation.skill)
            for operator in problem.operators
        ) <= 1:
            redundancy_penalty += 4.0
    score = (
        88
        + min(10, max(-45, slack_hours * 0.6))
        - average_failure * 35
        - order.quality_reject_rate * 100
        - min(12, redundancy_penalty)
        - (4 if any(task.is_overtime for task in tasks) else 0)
        - (3 if any(task.uses_generator for task in tasks) else 0)
    )
    return round(max(5.0, min(99.0, score)), 1)


def _attractiveness(
    order: Order,
    financial: Any,
    confidence: float,
    displacement: float,
) -> AttractivenessScore:
    production_cost = (
        financial.material_cost
        + financial.regular_labour_cost
        + financial.overtime_cost
        + financial.machine_cost
        + financial.grid_energy_cost
        + financial.generator_cost
        + financial.changeover_cost
        + financial.expected_rework_cost
    )
    contribution = order.selling_price - production_cost
    reliability_risk = max(0.0, contribution) * (1 - confidence / 100)
    strategic_value = min(
        order.selling_price * 0.15,
        max(0.0, order.strategic_weight - 1) * 25_000,
    )
    raw = (
        contribution
        - financial.late_penalty
        - displacement
        - reliability_risk
        + strategic_value
    )
    score = max(0.0, min(100.0, 50 + 50 * raw / max(1, order.selling_price)))
    return AttractivenessScore(
        score=round(score, 1),
        expected_contribution_margin=round(contribution, 2),
        expected_late_penalty=round(financial.late_penalty + displacement, 2),
        overtime_cost=financial.overtime_cost,
        generator_cost=financial.generator_cost,
        changeover_cost=financial.changeover_cost,
        reliability_risk_cost=round(reliability_risk, 2),
        strategic_value=round(strategic_value, 2),
    )


def _hard_constraint_notes(problem: PlanningProblem, order: Order) -> list[str]:
    notes: list[str] = []
    for operation in order.operations:
        machines = [
            machine
            for machine in problem.machines
            if machine.can_process(operation.operation_type)
            and (
                not operation.eligible_machine_ids
                or machine.id in operation.eligible_machine_ids
            )
        ]
        operators = [
            operator
            for machine in machines
            for operator in problem.operators
            if operator.is_qualified(machine, operation.skill)
        ]
        notes.append(
            f"{operation.operation_type}: {len(machines)} compatible machine(s), {len({operator.id for operator in operators})} qualified operator(s)"
        )
    if order.release_at:
        notes.append(f"Material release: {order.release_at.isoformat()}")
    return notes


def _capability_gaps(problem: PlanningProblem, order: Order) -> list[str]:
    gaps: list[str] = []
    for operation in order.operations:
        compatible = [
            machine
            for machine in problem.machines
            if machine.can_process(operation.operation_type)
            and (
                not operation.eligible_machine_ids
                or machine.id in operation.eligible_machine_ids
            )
        ]
        if not compatible:
            gaps.append(f"No machine can perform {operation.operation_type}")
            continue
        if not any(
            operator.is_qualified(machine, operation.skill)
            for machine in compatible
            for operator in problem.operators
        ):
            gaps.append(f"No eligible operator is available for {operation.operation_type}")
    return gaps

