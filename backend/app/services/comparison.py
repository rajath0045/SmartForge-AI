"""Run and explain the three required optimization modes."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.optimizer.domain import PlanningProblem, ScheduleMode, ScheduleResult
from app.optimizer.scheduler import SchedulingEngine


@dataclass(frozen=True, slots=True)
class PlanComparisonRow:
    mode: str
    feasible: bool
    valid: bool
    production_cost: float
    expected_profit: float
    overtime_cost: float
    penalties: float
    generator_cost: float
    on_time_delivery_pct: float
    changeover_cost: float
    breakdown_exposure: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class PlanComparison:
    rows: list[PlanComparisonRow]
    recommended_mode: str | None
    explanation: str
    results: dict[str, ScheduleResult]

    def as_dict(self, *, include_tasks: bool = False) -> dict[str, object]:
        data: dict[str, object] = {
            "plans": [row.as_dict() for row in self.rows],
            "recommended_mode": self.recommended_mode,
            "explanation": self.explanation,
        }
        if include_tasks:
            data["results"] = self.results
        return data


def compare_modes(
    problem: PlanningProblem,
    engine: SchedulingEngine | None = None,
) -> PlanComparison:
    engine = engine or SchedulingEngine()
    results: dict[str, ScheduleResult] = {}
    rows: list[PlanComparisonRow] = []
    for mode in (
        ScheduleMode.CHEAPEST,
        ScheduleMode.MOST_ON_TIME,
        ScheduleMode.MOST_ROBUST,
    ):
        result = engine.generate(problem, mode)
        mode_name = str(getattr(mode, "value", mode))
        results[mode_name] = result
        metrics = result.metrics
        exposure = _breakdown_exposure(problem, result)
        rows.append(
            PlanComparisonRow(
                mode=mode_name,
                feasible=result.feasible,
                valid=result.valid,
                production_cost=float(metrics.get("production_cost", 0.0)),
                expected_profit=float(metrics.get("expected_profit", 0.0)),
                overtime_cost=float(metrics.get("overtime_cost", 0.0)),
                penalties=float(metrics.get("late_penalties", 0.0)),
                generator_cost=float(metrics.get("generator_cost", 0.0)),
                on_time_delivery_pct=float(metrics.get("on_time_delivery_pct", 0.0)),
                changeover_cost=float(metrics.get("changeover_cost", 0.0)),
                breakdown_exposure=round(exposure, 2),
            )
        )

    viable = [row for row in rows if row.feasible and row.valid]
    if not viable:
        return PlanComparison(
            rows,
            None,
            "No mode produced a complete validated schedule; resolve hard capacity or material constraints first.",
            results,
        )
    # Management utility preserves economics but prices service and reliability.
    def utility(row: PlanComparisonRow) -> float:
        # Exposure is weighted above its arithmetic expectation because a
        # bottleneck failure creates correlated commercial harm (expediting,
        # customer escalation and downstream starvation) not fully captured
        # by the direct penalty estimate.
        return (
            row.expected_profit
            + row.on_time_delivery_pct * 2_000
            - row.breakdown_exposure * 1.5
        )

    recommended = max(viable, key=lambda row: (utility(row), row.mode))
    cheapest = next(row for row in rows if row.mode == "CHEAPEST")
    on_time = next(row for row in rows if row.mode == "MOST_ON_TIME")
    robust = next(row for row in rows if row.mode == "MOST_ROBUST")
    explanation = (
        f"Recommend {recommended.mode}: it provides the strongest risk-adjusted management utility. "
        f"CHEAPEST costs ₹{cheapest.production_cost:,.0f}; MOST_ON_TIME reaches "
        f"{on_time.on_time_delivery_pct:.1f}% on-time delivery; MOST_ROBUST limits modeled "
        f"breakdown exposure to ₹{robust.breakdown_exposure:,.0f}."
    )
    return PlanComparison(rows, recommended.mode, explanation, results)


def _breakdown_exposure(problem: PlanningProblem, result: ScheduleResult) -> float:
    exposure = 0.0
    for task in result.tasks:
        machine = problem.machine_map.get(task.machine_id)
        order = problem.order_map.get(task.order_id)
        if machine is None or order is None:
            continue
        task_fraction = task.duration_minutes / max(
            1,
            sum(
                other.duration_minutes
                for other in result.tasks
                if other.order_id == task.order_id
            ),
        )
        exposure += (
            machine.failure_probability
            * (order.late_penalty_per_day + order.selling_price * 0.05)
            * task_fraction
        )
    return exposure
