"""Economic generator dispatch decisions with an auditable inequality."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.optimizer.domain import PlanningProblem


@dataclass(frozen=True, slots=True)
class GeneratorDecision:
    should_run: bool
    machine_id: str
    runtime_minutes: int
    generator_cost: float
    additional_operating_cost: float
    avoided_penalty: float
    protected_contribution_margin: float
    net_benefit: float
    affected_orders: tuple[str, ...]
    explanation: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_generator_decision(
    problem: PlanningProblem,
    *,
    machine_id: str,
    runtime_minutes: int,
    affected_order_ids: list[str] | tuple[str, ...],
    avoided_delay_minutes: int,
    protected_contribution_margin: float = 0.0,
    additional_operating_cost: float = 0.0,
) -> GeneratorDecision:
    if machine_id not in problem.machine_map:
        raise ValueError(f"unknown machine {machine_id}")
    if runtime_minutes <= 0 or avoided_delay_minutes < 0:
        raise ValueError("runtime must be positive and avoided delay cannot be negative")
    machine = problem.machine_map[machine_id]
    orders = [problem.order_map[order_id] for order_id in affected_order_ids]
    generator_cost = (
        runtime_minutes
        / 60
        * machine.power_kw
        * problem.costs.generator_cost_per_kwh
    )
    avoided_penalty = sum(
        order.late_penalty_per_day * avoided_delay_minutes / 1440 for order in orders
    )
    benefit = avoided_penalty + max(0.0, protected_contribution_margin)
    cost = generator_cost + max(0.0, additional_operating_cost)
    net = benefit - cost
    should_run = net > 0
    action = "Run" if should_run else "Do not run"
    explanation = (
        f"{action} the generator for {machine_id}: ₹{benefit:,.0f} of avoided penalty/protected "
        f"margin {'exceeds' if should_run else 'does not exceed'} ₹{cost:,.0f} generator and "
        f"incremental operating cost (net ₹{net:,.0f})."
    )
    return GeneratorDecision(
        should_run=should_run,
        machine_id=machine_id,
        runtime_minutes=runtime_minutes,
        generator_cost=round(generator_cost, 2),
        additional_operating_cost=round(additional_operating_cost, 2),
        avoided_penalty=round(avoided_penalty, 2),
        protected_contribution_margin=round(protected_contribution_margin, 2),
        net_benefit=round(net, 2),
        affected_orders=tuple(affected_order_ids),
        explanation=explanation,
    )

