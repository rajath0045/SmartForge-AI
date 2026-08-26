"""Explainable current/future risk detection and financially justified actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Iterable

from app.optimizer.domain import PlanningProblem, ScheduleResult, ScheduleTask

from .capacity import calculate_machine_capacity, identify_bottleneck
from .financial import calculate_schedule_financials


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class RiskIssue:
    id: str
    timing: str
    severity: RiskSeverity
    category: str
    title: str
    probability: float
    expected_financial_loss: float
    affected_orders: tuple[str, ...]
    affected_machines: tuple[str, ...]
    delivery_impact: str
    recommended_action: str
    financial_justification: str

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(frozen=True, slots=True)
class Recommendation:
    id: str
    severity: RiskSeverity
    action: str
    reason: str
    expected_benefit: float
    estimated_cost: float
    net_benefit: float
    affected_orders: tuple[str, ...]
    requires_approval: bool = True

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(frozen=True, slots=True)
class OwnerCall:
    call: str
    reason: str
    expected_value_protected: float
    related_risk_id: str | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def analyze_risks(
    problem: PlanningProblem,
    schedule: ScheduleResult | Iterable[ScheduleTask],
) -> list[RiskIssue]:
    tasks = list(schedule.tasks if isinstance(schedule, ScheduleResult) else schedule)
    financials = calculate_schedule_financials(problem, tasks)
    risks: list[RiskIssue] = []

    for order_id, item in financials.by_order.items():
        if not item.completion_at:
            continue
        order = problem.order_map[order_id]
        slack_minutes = round((order.due_at - item.completion_at).total_seconds() / 60)
        if item.lateness_minutes > 0:
            severity = (
                RiskSeverity.CRITICAL
                if _is_tier_1(order.customer_tier) or item.late_penalty >= 50_000
                else RiskSeverity.HIGH
            )
            risks.append(
                RiskIssue(
                    id=f"DELIVERY-{order_id}",
                    timing="CURRENT",
                    severity=severity,
                    category="DELIVERY",
                    title=f"{order_id} is scheduled late",
                    probability=1.0,
                    expected_financial_loss=item.late_penalty,
                    affected_orders=(order_id,),
                    affected_machines=tuple(
                        sorted({task.machine_id for task in tasks if task.order_id == order_id})
                    ),
                    delivery_impact=f"Expected completion is {item.lateness_minutes / 60:.1f} hours late",
                    recommended_action="Prioritize the remaining route, then compare targeted overtime with the contractual penalty",
                    financial_justification=f"Current schedule exposes ₹{item.late_penalty:,.0f} in late-delivery penalties",
                )
            )
        elif slack_minutes <= 8 * 60:
            probability = max(0.2, min(0.85, 0.65 - slack_minutes / (24 * 60)))
            exposure = order.late_penalty_per_day * probability
            risks.append(
                RiskIssue(
                    id=f"SLACK-{order_id}",
                    timing="FUTURE",
                    severity=RiskSeverity.HIGH if probability >= 0.55 else RiskSeverity.MEDIUM,
                    category="DELIVERY",
                    title=f"{order_id} has little delivery buffer",
                    probability=round(probability, 3),
                    expected_financial_loss=round(exposure, 2),
                    affected_orders=(order_id,),
                    affected_machines=tuple(
                        sorted({task.machine_id for task in tasks if task.order_id == order_id})
                    ),
                    delivery_impact=f"Only {max(0, slack_minutes) / 60:.1f} hours of schedule slack remain",
                    recommended_action="Protect its constrained operations from lower-impact work",
                    financial_justification=f"Risk-adjusted one-day penalty exposure is ₹{exposure:,.0f}",
                )
            )

    for capacity in calculate_machine_capacity(problem, tasks):
        if capacity.utilization_pct < 85:
            continue
        machine = problem.machine_map[capacity.resource_id]
        affected = tuple(
            sorted({task.order_id for task in tasks if task.machine_id == machine.id})
        )
        dependent_penalty = sum(
            problem.order_map[order_id].late_penalty_per_day for order_id in affected
        )
        probability = min(0.95, max(0.45, capacity.utilization_pct / 110))
        expected_loss = dependent_penalty * probability
        risks.append(
            RiskIssue(
                id=f"CAPACITY-{machine.id}",
                timing="FUTURE",
                severity=(
                    RiskSeverity.CRITICAL
                    if capacity.utilization_pct >= 95
                    else RiskSeverity.HIGH
                ),
                category="BOTTLENECK",
                title=f"{machine.id} loading is {capacity.utilization_pct:.1f}%",
                probability=round(probability, 3),
                expected_financial_loss=round(expected_loss, 2),
                affected_orders=affected,
                affected_machines=(machine.id,),
                delivery_impact=f"Only {capacity.remaining_minutes / 60:.1f} finite-capacity hours remain",
                recommended_action="Group same-family work and approve overtime only where avoided penalties exceed its cost",
                financial_justification=f"Orders on this resource carry ₹{dependent_penalty:,.0f}/day of combined penalty exposure",
            )
        )

    for machine in problem.machines:
        probability = max(machine.failure_probability, (100 - machine.health_score) / 100)
        if probability < 0.25 and machine.health_score >= 70:
            continue
        affected = tuple(
            sorted({task.order_id for task in tasks if task.machine_id == machine.id})
        )
        revenue = sum(problem.order_map[order_id].selling_price for order_id in affected)
        impact = revenue * min(0.25, probability * 0.2)
        risks.append(
            RiskIssue(
                id=f"HEALTH-{machine.id}",
                timing="FUTURE",
                severity=RiskSeverity.HIGH if probability >= 0.45 else RiskSeverity.MEDIUM,
                category="MAINTENANCE",
                title=f"{machine.id} health requires attention",
                probability=round(min(1.0, probability), 3),
                expected_financial_loss=round(impact, 2),
                affected_orders=affected,
                affected_machines=(machine.id,),
                delivery_impact=f"A failure would interrupt {len(affected)} scheduled orders",
                recommended_action="Place preventive maintenance in the lowest-penalty idle window",
                financial_justification=f"Approximately ₹{impact:,.0f} of risk-adjusted revenue is exposed",
            )
        )

    for machine in problem.machines:
        for capability in machine.capabilities:
            qualified = [
                operator.id
                for operator in problem.operators
                if operator.is_qualified(machine, capability)
            ]
            if len(qualified) != 1:
                continue
            affected = tuple(
                sorted(
                    {
                        task.order_id
                        for task in tasks
                        if task.machine_id == machine.id
                        and task.operation_type.upper() == capability.upper()
                    }
                )
            )
            if not affected:
                continue
            exposure = sum(
                problem.order_map[order_id].late_penalty_per_day for order_id in affected
            ) * 0.18
            risks.append(
                RiskIssue(
                    id=f"SKILL-{machine.id}-{capability}",
                    timing="FUTURE",
                    severity=RiskSeverity.HIGH,
                    category="LABOUR",
                    title=f"Single qualified operator for {machine.id}",
                    probability=0.18,
                    expected_financial_loss=round(exposure, 2),
                    affected_orders=affected,
                    affected_machines=(machine.id,),
                    delivery_impact=f"Absence of {qualified[0]} removes usable {capability} capacity",
                    recommended_action=f"Cross-train a backup operator for {capability}",
                    financial_justification=f"A one-day absence has ₹{exposure:,.0f} risk-adjusted penalty exposure",
                )
            )

    for order in problem.orders:
        if order.release_at and order.release_at > problem.horizon_start:
            hours = (order.release_at - problem.horizon_start).total_seconds() / 3600
            if order.release_at >= order.due_at - timedelta(hours=8):
                exposure = order.late_penalty_per_day * 0.7
                risks.append(
                    RiskIssue(
                        id=f"MATERIAL-{order.id}",
                        timing="CURRENT",
                        severity=RiskSeverity.HIGH,
                        category="MATERIAL",
                        title=f"{order.id} is material constrained",
                        probability=0.7,
                        expected_financial_loss=round(exposure, 2),
                        affected_orders=(order.id,),
                        affected_machines=(),
                        delivery_impact=f"Material releases {hours:.1f} hours into the horizon near its due date",
                        recommended_action="Escalate the supplier and protect the first feasible production window",
                        financial_justification=f"A one-day slip costs ₹{order.late_penalty_per_day:,.0f}",
                    )
                )

    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
    }
    return sorted(
        _dedupe_risks(risks),
        key=lambda risk: (severity_order[risk.severity], -risk.expected_financial_loss, risk.id),
    )


def generate_recommendations(risks: Iterable[RiskIssue]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for index, risk in enumerate(risks, start=1):
        if risk.category == "LABOUR":
            estimated_cost = 45_000.0
            expected_benefit = risk.expected_financial_loss * 8
        elif risk.category == "MAINTENANCE":
            estimated_cost = max(8_000.0, risk.expected_financial_loss * 0.15)
            expected_benefit = risk.expected_financial_loss * 0.75
        elif risk.category in {"DELIVERY", "BOTTLENECK"}:
            estimated_cost = risk.expected_financial_loss * 0.25
            expected_benefit = risk.expected_financial_loss * 0.8
        else:
            estimated_cost = risk.expected_financial_loss * 0.1
            expected_benefit = risk.expected_financial_loss * 0.65
        recommendations.append(
            Recommendation(
                id=f"REC-{index:03d}",
                severity=risk.severity,
                action=risk.recommended_action,
                reason=f"{risk.title}. {risk.financial_justification}",
                expected_benefit=round(expected_benefit, 2),
                estimated_cost=round(estimated_cost, 2),
                net_benefit=round(expected_benefit - estimated_cost, 2),
                affected_orders=risk.affected_orders,
                requires_approval=risk.severity in {RiskSeverity.CRITICAL, RiskSeverity.HIGH},
            )
        )
    return sorted(recommendations, key=lambda item: (-item.net_benefit, item.id))


def owners_next_call(
    problem: PlanningProblem,
    schedule: ScheduleResult | Iterable[ScheduleTask],
    risks: Iterable[RiskIssue] | None = None,
) -> OwnerCall:
    tasks = list(schedule.tasks if isinstance(schedule, ScheduleResult) else schedule)
    risk_list = list(risks or analyze_risks(problem, tasks))
    if not risk_list:
        bottleneck = identify_bottleneck(problem, tasks)
        return OwnerCall(
            call="No external call required",
            reason=bottleneck.explanation,
            expected_value_protected=0.0,
            related_risk_id=None,
        )
    risk = max(risk_list, key=lambda item: item.expected_financial_loss)
    if risk.category == "MAINTENANCE":
        target = "Maintenance contractor"
    elif risk.category == "MATERIAL":
        target = "Raw material supplier"
    elif risk.category == "LABOUR":
        target = "Backup operator / training lead"
    elif risk.category == "DELIVERY" and risk.affected_orders:
        order = problem.order_map[risk.affected_orders[0]]
        target = f"Customer {order.customer_id}"
    else:
        target = "Approved outsourcing vendor"
    return OwnerCall(
        call=target,
        reason=f"{risk.title}. {risk.recommended_action}",
        expected_value_protected=round(risk.expected_financial_loss, 2),
        related_risk_id=risk.id,
    )


def _dedupe_risks(risks: list[RiskIssue]) -> list[RiskIssue]:
    return list({risk.id: risk for risk in risks}.values())


def _is_tier_1(tier: str) -> bool:
    return str(getattr(tier, "value", tier)).upper().replace("-", "_") in {
        "TIER_1",
        "TIER1",
    }

