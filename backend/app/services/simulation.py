"""Deterministic confidence simulation and what-if scenario comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from random import Random
from typing import Iterable, Mapping, Any

from app.optimizer.domain import PlanningProblem, ScheduleMode, ScheduleResult
from app.optimizer.scheduler import SchedulingEngine

from .financial import calculate_schedule_financials
from .replanning import (
    DisruptionEvent,
    ReplanResult,
    ReplanningService,
)


@dataclass(frozen=True, slots=True)
class DeliveryConfidence:
    order_id: str
    on_time_probability_pct: float
    simulated_mean_delay_minutes: float
    p90_delay_minutes: int
    risk: str
    iterations: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ScenarioResult:
    name: str
    replan: ReplanResult
    delivery_confidence: list[DeliveryConfidence]
    metrics: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "metrics": self.metrics,
            "delivery_confidence": [item.as_dict() for item in self.delivery_confidence],
            "difference": self.replan.difference.as_dict(),
            "explanation": self.replan.explanation,
        }


class DeliveryConfidenceSimulator:
    """Rule-grounded Monte Carlo simulation with a fixed default seed.

    It does not pretend to be an ML model.  Machine failure, absenteeism,
    quality, and material-delay probabilities are sampled transparently from
    the planning state/metadata.
    """

    def run(
        self,
        problem: PlanningProblem,
        schedule: ScheduleResult,
        *,
        iterations: int = 300,
        seed: int = 9173,
    ) -> list[DeliveryConfidence]:
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        rng = Random(seed)
        absence_probability = float(
            problem.metadata.get("absence_probability_per_operation", 0.025)
        )
        material_probabilities = problem.metadata.get("material_delay_probability", {})
        material_delay_minutes = int(problem.metadata.get("material_delay_minutes", 480))
        results: list[DeliveryConfidence] = []
        for order in sorted(problem.orders, key=lambda item: item.id):
            order_tasks = sorted(
                (task for task in schedule.tasks if task.order_id == order.id),
                key=lambda task: (task.start, task.id),
            )
            if not order_tasks:
                results.append(
                    DeliveryConfidence(order.id, 0.0, 0.0, 0, "CRITICAL", iterations)
                )
                continue
            planned_completion = max(task.end for task in order_tasks)
            delays: list[int] = []
            on_time = 0
            for _ in range(iterations):
                delay = 0
                for task in order_tasks:
                    machine = problem.machine_map[task.machine_id]
                    # Convert a per-horizon risk to a task exposure while
                    # preserving higher risk on long operations.
                    exposure = min(
                        0.85,
                        machine.failure_probability
                        * max(0.15, task.duration_minutes / 480),
                    )
                    if rng.random() < exposure:
                        delay += round(rng.triangular(60, 600, 210))
                    if rng.random() < absence_probability:
                        delay += round(rng.triangular(120, 480, 240))
                if rng.random() < order.quality_reject_rate:
                    delay += max(
                        30,
                        round(
                            sum(task.duration_minutes for task in order_tasks)
                            * max(0.15, order.quality_reject_rate * 5)
                        ),
                    )
                material_probability = float(
                    material_probabilities.get(order.id, 0.0)
                    if isinstance(material_probabilities, Mapping)
                    else 0.0
                )
                if rng.random() < material_probability:
                    delay += material_delay_minutes
                delays.append(delay)
                if planned_completion.timestamp() + delay * 60 <= order.due_at.timestamp():
                    on_time += 1
            ordered = sorted(delays)
            p90 = ordered[min(len(ordered) - 1, max(0, round(0.9 * len(ordered)) - 1))]
            confidence = round(100 * on_time / iterations, 1)
            results.append(
                DeliveryConfidence(
                    order_id=order.id,
                    on_time_probability_pct=confidence,
                    simulated_mean_delay_minutes=round(sum(delays) / len(delays), 1),
                    p90_delay_minutes=p90,
                    risk=_risk_from_confidence(confidence),
                    iterations=iterations,
                )
            )
        return results


class ScenarioSimulator:
    def __init__(
        self,
        engine: SchedulingEngine | None = None,
        confidence_simulator: DeliveryConfidenceSimulator | None = None,
    ) -> None:
        self.engine = engine or SchedulingEngine()
        self.replanner = ReplanningService(self.engine)
        self.confidence_simulator = confidence_simulator or DeliveryConfidenceSimulator()

    def run(
        self,
        name: str,
        problem: PlanningProblem,
        baseline: ScheduleResult,
        disruption: DisruptionEvent | Mapping[str, Any],
        *,
        mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
        iterations: int = 200,
        seed: int = 9173,
    ) -> ScenarioResult:
        replan = self.replanner.replan(problem, baseline, disruption, mode=mode)
        confidence = self.confidence_simulator.run(
            replan.revised_problem,
            replan.revised_schedule,
            iterations=iterations,
            seed=seed,
        )
        financials = calculate_schedule_financials(
            replan.revised_problem, replan.revised_schedule.tasks
        )
        metrics: dict[str, object] = financials.as_dict()
        metrics["average_delivery_confidence_pct"] = round(
            sum(item.on_time_probability_pct for item in confidence)
            / max(1, len(confidence)),
            1,
        )
        metrics["valid_schedule"] = replan.revised_schedule.valid
        return ScenarioResult(name, replan, confidence, metrics)

    def compare(
        self,
        problem: PlanningProblem,
        baseline: ScheduleResult,
        scenarios: Iterable[
            tuple[str, DisruptionEvent | Mapping[str, Any]]
        ],
        *,
        mode: ScheduleMode | str = ScheduleMode.MOST_ON_TIME,
        iterations: int = 150,
        seed: int = 9173,
    ) -> list[ScenarioResult]:
        return [
            self.run(
                name,
                problem,
                baseline,
                disruption,
                mode=mode,
                iterations=iterations,
                seed=seed + index,
            )
            for index, (name, disruption) in enumerate(scenarios)
        ]


def simulate_delivery_confidence(
    problem: PlanningProblem,
    schedule: ScheduleResult,
    *,
    iterations: int = 300,
    seed: int = 9173,
) -> list[DeliveryConfidence]:
    return DeliveryConfidenceSimulator().run(
        problem, schedule, iterations=iterations, seed=seed
    )


def _risk_from_confidence(confidence: float) -> str:
    if confidence < 55:
        return "CRITICAL"
    if confidence < 75:
        return "HIGH"
    if confidence < 90:
        return "MEDIUM"
    return "LOW"

