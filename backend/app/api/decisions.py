"""Live decision-support endpoints backed by the finite-capacity optimizer.

The existing read endpoints expose the deterministic seed snapshot.  This
router is deliberately separate: every response below is recalculated from
the current ORM state, using the pure planning-domain adapter and services.
Interactive requests use the validated deterministic heuristic so they remain
inside the frontend timeout; callers can explicitly request a bounded CP-SAT
solve from ``/schedule/generate``.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta
from math import ceil
from statistics import median
from time import perf_counter
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.core.enums import ScheduleMode, ScheduleStatus
from app.models import (
    ChangeoverMatrix,
    CostConfiguration,
    Machine as MachineRecord,
    Operator as OperatorRecord,
    OrderOperation,
    PowerEvent,
    ProductionOrder,
    Schedule,
    Shift,
)
from app.optimizer.domain import (
    CalendarWindow,
    Machine,
    Operation,
    Operator,
    Order,
    PlanningProblem,
    ScheduleResult,
    SolverKind,
    problem_from_records,
)
from app.optimizer.scheduler import SchedulingEngine
from app.services.capacity import calculate_machine_capacity, identify_bottleneck
from app.services.comparison import compare_modes
from app.services.financial import calculate_schedule_financials
from app.services.replanning import (
    DisruptionEvent,
    DisruptionKind,
    ReplanResult,
    ReplanningService,
)
from app.services.rfq import OrderAcceptanceService
from app.services.simulation import ScenarioSimulator

router = APIRouter(tags=["decision intelligence"])


class _RequestModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ScheduleGenerateRequest(_RequestModel):
    mode: str = ScheduleMode.MOST_ON_TIME.value
    exact: bool = False
    max_solve_seconds: float = Field(
        8.0, alias="maxSolveSeconds", ge=0.1, le=20.0
    )


class RfqRequest(_RequestModel):
    customer: str = Field(min_length=1, max_length=140)
    tier: str = Field(min_length=1, max_length=24)
    part: str = Field(min_length=1, max_length=50)
    quantity: int = Field(gt=0, le=100_000)
    requested_date: date = Field(alias="requestedDate")
    selling_price: float = Field(alias="sellingPrice", gt=0)
    late_penalty: float = Field(alias="latePenalty", ge=0)
    operations: list[str] = Field(min_length=1, max_length=20)
    material_available: bool = Field(alias="materialAvailable")


class DisruptionRequest(_RequestModel):
    type: str
    resource: str = ""
    start: datetime
    duration_hours: float = Field(alias="durationHours", gt=0, le=336)
    notes: str = ""
    mode: str = ScheduleMode.MOST_ON_TIME.value
    generator_available: bool = Field(True, alias="generatorAvailable")
    generator_capacity_kw: float | None = Field(
        None, alias="generatorCapacityKw", gt=0
    )


class SimulationRequest(_RequestModel):
    scenario: str = Field(min_length=1, max_length=80)
    magnitude: float = Field(gt=0, le=100)


def _mode(value: str) -> ScheduleMode:
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "ONTIME": ScheduleMode.MOST_ON_TIME.value,
        "ON_TIME": ScheduleMode.MOST_ON_TIME.value,
        "ROBUST": ScheduleMode.MOST_ROBUST.value,
    }
    try:
        return ScheduleMode(aliases.get(normalized, normalized))
    except ValueError as exc:
        supported = ", ".join(item.value for item in ScheduleMode)
        raise HTTPException(
            status_code=422, detail=f"Unsupported schedule mode; use {supported}"
        ) from exc


def _record_list(db: Session, statement: Any) -> list[Any]:
    return list(db.scalars(statement).unique().all())


def _load_problem(db: Session) -> tuple[PlanningProblem, list[ProductionOrder]]:
    """Eagerly load the digital-twin records and adapt them after one DB pass."""

    schedule = db.scalar(
        select(Schedule)
        .where(Schedule.status == ScheduleStatus.ACTIVE)
        .order_by(Schedule.generated_at.desc(), Schedule.id.desc())
    )
    orders = _record_list(
        db,
        select(ProductionOrder)
        .options(
            joinedload(ProductionOrder.customer),
            joinedload(ProductionOrder.part_family),
            selectinload(ProductionOrder.operations).selectinload(
                OrderOperation.eligible_machines
            ),
        )
        .order_by(ProductionOrder.id),
    )
    if schedule is not None:
        horizon_start, horizon_end = schedule.horizon_start, schedule.horizon_end
    elif orders:
        first_release = min(order.material_available_date for order in orders)
        horizon_start = datetime.combine(first_release.date(), time(6))
        horizon_end = horizon_start + timedelta(days=14)
    else:
        raise HTTPException(
            status_code=503,
            detail="No production orders are configured; seed or import shop data first",
        )

    machines = _record_list(
        db,
        select(MachineRecord)
        .options(
            selectinload(MachineRecord.capabilities),
            selectinload(MachineRecord.breakdowns),
            selectinload(MachineRecord.maintenance_windows),
        )
        .order_by(MachineRecord.id),
    )
    operators = _record_list(
        db,
        select(OperatorRecord)
        .options(
            joinedload(OperatorRecord.shift),
            selectinload(OperatorRecord.skills),
            selectinload(OperatorRecord.availability),
        )
        .order_by(OperatorRecord.id),
    )
    shifts = _record_list(db, select(Shift).order_by(Shift.id))
    power = _record_list(db, select(PowerEvent).order_by(PowerEvent.start_at))
    changeovers = _record_list(
        db, select(ChangeoverMatrix).order_by(ChangeoverMatrix.id)
    )
    costs = _record_list(
        db, select(CostConfiguration).order_by(CostConfiguration.key)
    )
    if not machines or not operators or not shifts:
        raise HTTPException(
            status_code=503,
            detail="Machine, operator, and shift master data must be configured",
        )

    return (
        problem_from_records(
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            machines=machines,
            operators=operators,
            orders=orders,
            shifts=shifts,
            power_windows=power,
            changeovers=changeovers,
            costs=costs,
        ),
        orders,
    )


def _engine(*, exact: bool = False, max_seconds: float = 8.0) -> SchedulingEngine:
    return SchedulingEngine(
        prefer_cp_sat=exact,
        max_solve_seconds=min(20.0, max(0.1, max_seconds)),
    )


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _camel_key(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item[:1].upper() + item[1:] for item in tail)


def _camel(value: Any) -> Any:
    if isinstance(value, dict):
        return {_camel_key(str(key)): _camel(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_camel(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _violations(result: ScheduleResult) -> list[dict[str, Any]]:
    return [
        {
            "code": _value(item.code),
            "message": item.message,
            "taskIds": list(item.task_ids),
            "resourceId": item.resource_id,
        }
        for item in result.violations
    ]


def _solver_policy(result: ScheduleResult, *, requested_exact: bool) -> dict[str, Any]:
    fallback = requested_exact and result.solver != SolverKind.CP_SAT
    if not requested_exact:
        explanation = (
            "Deterministic validated finite-capacity heuristic selected for the "
            "interactive response; send exact=true to run bounded CP-SAT."
        )
    elif fallback:
        relevant = next(
            (
                line
                for line in result.diagnostics
                if "fallback" in line.lower()
                or "unavailable" in line.lower()
                or "no incumbent" in line.lower()
            ),
            "CP-SAT did not return a usable incumbent inside the bound; the validated heuristic was returned.",
        )
        explanation = relevant
    else:
        explanation = "Bounded CP-SAT completed and its concrete schedule was independently validated."
    return {
        "requestedExact": requested_exact,
        "usedFallback": fallback,
        "explanation": explanation,
    }


def _task_payload(problem: PlanningProblem, task: Any) -> dict[str, Any]:
    operation = problem.operation_map.get(task.operation_id)
    order = problem.order_map.get(task.order_id)
    return {
        "id": task.id,
        "operationId": task.operation_id,
        "orderOperationId": task.operation_id,
        "orderId": task.order_id,
        "customerTier": order.customer_tier if order else None,
        "partFamily": task.part_family,
        "operationType": task.operation_type,
        "sequence": operation.sequence if operation else None,
        "machineId": task.machine_id,
        "operatorId": task.operator_id,
        "startAt": task.start.isoformat(),
        "endAt": task.end.isoformat(),
        "durationMinutes": task.duration_minutes,
        "quantity": task.quantity,
        "status": task.status,
        "shiftId": task.shift_name,
        "isOvertime": task.is_overtime,
        "isSunday": task.is_sunday,
        "usesGenerator": task.uses_generator,
        "changeoverMinutes": task.changeover_minutes,
        "changeoverCost": task.changeover_cost,
        "robustBufferMinutes": task.robust_buffer_minutes,
        "isFrozen": task.is_frozen,
    }


def _schedule_payload(
    problem: PlanningProblem,
    result: ScheduleResult,
    *,
    requested_exact: bool,
    elapsed_ms: float | None = None,
) -> dict[str, Any]:
    operations = [_task_payload(problem, task) for task in result.tasks]
    payload: dict[str, Any] = {
        "mode": _value(result.mode),
        "solver": _value(result.solver),
        "solverStatus": _value(result.status),
        "status": _value(result.status),
        "valid": result.valid,
        "isValid": result.valid,
        "violations": _violations(result),
        "validationErrors": [item["message"] for item in _violations(result)],
        "diagnostics": list(result.diagnostics),
        "solverPolicy": _solver_policy(result, requested_exact=requested_exact),
        "objectiveValue": result.objective_value,
        "generatedAt": result.generated_at.isoformat()
        if result.generated_at
        else None,
        "horizonStart": problem.horizon_start.isoformat(),
        "horizonEnd": problem.horizon_end.isoformat(),
        "metrics": _camel(result.metrics),
        "operations": operations,
        "tasks": operations,
    }
    if elapsed_ms is not None:
        payload["elapsedMs"] = round(elapsed_ms, 1)
    return payload


@router.post("/schedule/generate")
def generate_schedule(
    request: ScheduleGenerateRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    request = request or ScheduleGenerateRequest()
    problem, _ = _load_problem(db)
    started = perf_counter()
    result = _engine(
        exact=request.exact, max_seconds=request.max_solve_seconds
    ).generate(problem, _mode(request.mode))
    return _schedule_payload(
        problem,
        result,
        requested_exact=request.exact,
        elapsed_ms=(perf_counter() - started) * 1_000,
    )


def _normalize_operation(value: str) -> str:
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "CNC": "TURNING",
        "LATHE": "TURNING",
        "DRILL": "DRILLING",
        "GRINDER": "GRINDING",
        "QUALITY": "INSPECTION",
    }
    return aliases.get(normalized, normalized)


def _rfq_order(
    request: RfqRequest,
    problem: PlanningProblem,
    records: Iterable[ProductionOrder],
) -> Order:
    due_at = datetime.combine(request.requested_date, time(18))
    if due_at <= problem.horizon_start:
        raise HTTPException(
            status_code=422,
            detail="requestedDate must fall after the planning horizon starts",
        )
    profiles: dict[str, list[tuple[float, int]]] = {}
    rows = list(records)
    for order in rows:
        for operation in order.operations:
            kind = _normalize_operation(str(_value(operation.operation_type)))
            profiles.setdefault(kind, []).append(
                (float(operation.run_minutes_per_unit), int(operation.setup_minutes))
            )

    order_id = "RFQ-LIVE-" + "".join(
        character for character in request.part.upper() if character.isalnum()
    )[:12]
    operations: list[Operation] = []
    predecessor: str | None = None
    for index, raw_kind in enumerate(request.operations, start=1):
        kind = _normalize_operation(raw_kind)
        observations = profiles.get(kind, ())
        run_per_unit = median(item[0] for item in observations) if observations else 0.25
        setup_minutes = round(median(item[1] for item in observations)) if observations else 30
        operation_id = f"{order_id}-OP-{index}"
        operations.append(
            Operation(
                id=operation_id,
                order_id=order_id,
                sequence=index,
                operation_type=kind,
                processing_minutes=max(15, ceil(run_per_unit * request.quantity)),
                required_skill=kind,
                predecessor_ids=(predecessor,) if predecessor else (),
                setup_minutes=max(0, setup_minutes),
                quantity=request.quantity,
            )
        )
        predecessor = operation_id

    matching_customer = next(
        (
            order.customer
            for order in rows
            if order.customer.name.casefold() == request.customer.casefold()
        ),
        None,
    )
    normalized_tier = request.tier.upper().replace(" ", "_").replace("-", "_")
    if normalized_tier in {"TIER1", "1"}:
        normalized_tier = "TIER_1"
    elif normalized_tier in {"TIER2", "2"}:
        normalized_tier = "TIER_2"
    elif normalized_tier in {"TIER3", "3"}:
        normalized_tier = "TIER_3"
    if normalized_tier not in {"TIER_1", "TIER_2", "TIER_3"}:
        raise HTTPException(status_code=422, detail="tier must be Tier 1, Tier 2, or Tier 3")

    material_ratios = [
        order.material_cost / order.revenue
        for order in rows
        if order.revenue > 0 and order.material_cost >= 0
    ]
    material_ratio = median(material_ratios) if material_ratios else 0.35
    material_ratio = max(0.15, min(0.65, material_ratio))
    release_at = (
        problem.horizon_start
        if request.material_available
        else problem.horizon_start + timedelta(days=2)
    )
    return Order(
        id=order_id,
        customer_id=matching_customer.id if matching_customer else "RFQ-CUSTOMER",
        customer_tier=normalized_tier,
        part_family=f"RFQ-{request.part.upper()}",
        quantity=request.quantity,
        due_at=due_at,
        operations=tuple(operations),
        release_at=release_at,
        selling_price=request.selling_price,
        material_cost=round(request.selling_price * material_ratio, 2),
        late_penalty_per_day=request.late_penalty,
        strategic_weight={"TIER_1": 1.8, "TIER_2": 1.2, "TIER_3": 0.9}[
            normalized_tier
        ],
        priority={"TIER_1": 5, "TIER_2": 3, "TIER_3": 1}[normalized_tier],
        quality_reject_rate=0.03,
    )


def _risk_state(status: str) -> str:
    return {
        "HEALTHY": "LOW",
        "WATCH": "MEDIUM",
        "HIGH": "HIGH",
        "CRITICAL": "CRITICAL",
    }.get(status, "MEDIUM")


@router.post("/rfq/evaluate")
def evaluate_rfq(request: RfqRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    problem, records = _load_problem(db)
    proposed = _rfq_order(request, problem, records)
    engine = _engine(exact=False)
    # Capable-to-promise is tested against the approved risk-protected policy,
    # so a profitable RFQ cannot silently consume the reserve that makes the
    # current commitments robust.
    baseline = engine.generate(problem, ScheduleMode.MOST_ROBUST)
    evaluation = OrderAcceptanceService(engine).evaluate(
        problem,
        proposed,
        baseline_schedule=baseline,
        mode=ScheduleMode.MOST_ROBUST,
    )
    trial_problem = problem.with_orders((*problem.orders, proposed))
    trial = evaluation.schedule or baseline
    capacities = calculate_machine_capacity(trial_problem, trial)
    bottleneck = identify_bottleneck(trial_problem, trial)
    qualified_counts = []
    for operation in proposed.operations:
        pairs = {
            operator.id
            for machine in trial_problem.machines
            if machine.can_process(operation.operation_type)
            for operator in trial_problem.operators
            if operator.is_qualified(machine, operation.skill)
        }
        qualified_counts.append(len(pairs))
    minimum_qualified = min(qualified_counts, default=0)
    bottleneck_capacity = capacities[0] if capacities else None
    reasons = list(evaluation.reasons)
    if bottleneck.utilization_pct >= 95:
        reasons.append(
            f"The order remains feasible inside the robust buffers, but raises "
            f"{bottleneck.machine_id} to {bottleneck.utilization_pct:.1f}% "
            "health-adjusted protected capacity; block the next grinding RFQ "
            "unless overtime or outsourcing restores reserve."
        )
    capacity_checks = [
        {
            "label": "Machine capacity",
            "value": (
                f"{bottleneck_capacity.remaining_minutes / 60:.1f} h slack on "
                f"{bottleneck_capacity.resource_id}"
                if bottleneck_capacity
                else "No machine capacity configured"
            ),
            "state": _risk_state(bottleneck_capacity.status)
            if bottleneck_capacity
            else "CRITICAL",
        },
        {
            "label": "Current bottleneck",
            "value": f"{bottleneck.machine_id or 'N/A'} · {bottleneck.utilization_pct:.1f}% health-adjusted projected",
            "state": "CRITICAL"
            if bottleneck.utilization_pct >= 95
            else "HIGH"
            if bottleneck.utilization_pct >= 85
            else "MEDIUM",
        },
        {
            "label": "Qualified labour",
            "value": f"Minimum {minimum_qualified} qualified operator(s) across the route",
            "state": "CRITICAL"
            if minimum_qualified == 0
            else "HIGH"
            if minimum_qualified == 1
            else "MEDIUM"
            if minimum_qualified <= 2
            else "LOW",
        },
        {
            "label": "Material",
            "value": "Available at horizon start"
            if request.material_available
            else "Modeled with a two-day material lead time",
            "state": "LOW" if request.material_available else "HIGH",
        },
    ]
    recommended = evaluation.recommended_promise_at or evaluation.requested_delivery_at
    return {
        "decision": evaluation.decision.value,
        "confidence": evaluation.delivery_confidence_pct,
        "score": evaluation.attractiveness.score,
        "requestedDate": evaluation.requested_delivery_at.date().isoformat(),
        "recommendedDate": recommended.date().isoformat(),
        "revenue": evaluation.estimated_revenue,
        "productionCost": evaluation.expected_production_cost,
        "overtimeCost": evaluation.overtime_cost,
        "generatorCost": evaluation.generator_cost,
        "expectedPenalty": evaluation.expected_penalty_exposure,
        "contributionMargin": evaluation.expected_contribution_margin,
        "bottleneckLoad": bottleneck.utilization_pct,
        "reasons": reasons,
        "capacityChecks": capacity_checks,
        "constraints": evaluation.constraints,
        "attractiveness": _camel(asdict(evaluation.attractiveness)),
        "solver": _value(trial.solver),
        "status": _value(trial.status),
        "valid": trial.valid,
        "violations": _violations(trial),
        "solverPolicy": _solver_policy(trial, requested_exact=False),
    }


def _resource_token(value: str) -> str:
    return value.split("·", 1)[0].strip().split()[0] if value.strip() else ""


def _disruption_event(
    request: DisruptionRequest, problem: PlanningProblem
) -> DisruptionEvent:
    raw_kind = request.type.strip().upper().replace("-", "_").replace(" ", "_")
    raw_kind = "QUALITY_FAILURE" if raw_kind == "QUALITY_REWORK" else raw_kind
    try:
        kind = DisruptionKind(raw_kind)
    except ValueError as exc:
        supported = ", ".join(
            [
                "MACHINE_BREAKDOWN",
                "OPERATOR_ABSENCE",
                "MATERIAL_DELAY",
                "QUALITY_REWORK",
                "POWER_CUT",
            ]
        )
        raise HTTPException(
            status_code=422, detail=f"Unsupported disruption type; use {supported}"
        ) from exc
    if not (problem.horizon_start <= request.start < problem.horizon_end):
        raise HTTPException(
            status_code=422,
            detail=(
                "start must fall inside the current planning horizon "
                f"({problem.horizon_start.isoformat()} to {problem.horizon_end.isoformat()})"
            ),
        )
    end_at = min(
        problem.horizon_end,
        request.start + timedelta(hours=request.duration_hours),
    )
    token = _resource_token(request.resource)
    machine_id = token if kind == DisruptionKind.MACHINE_BREAKDOWN else None
    operator_id = token if kind == DisruptionKind.OPERATOR_ABSENCE else None
    order_id = token if kind in {DisruptionKind.MATERIAL_DELAY, DisruptionKind.QUALITY_FAILURE} else None
    if kind == DisruptionKind.MACHINE_BREAKDOWN and machine_id not in problem.machine_map:
        raise HTTPException(status_code=422, detail=f"Unknown machine resource {token!r}")
    if kind == DisruptionKind.OPERATOR_ABSENCE and operator_id not in problem.operator_map:
        raise HTTPException(status_code=422, detail=f"Unknown operator resource {token!r}")
    if kind in {DisruptionKind.MATERIAL_DELAY, DisruptionKind.QUALITY_FAILURE} and order_id not in problem.order_map:
        raise HTTPException(status_code=422, detail=f"Unknown order resource {token!r}")
    rejected = 0
    operation_type = None
    rework_minutes = None
    if kind == DisruptionKind.QUALITY_FAILURE and order_id:
        order = problem.order_map[order_id]
        rejected = max(1, round(order.quantity * 0.05))
        last = max(order.operations, key=lambda item: item.sequence)
        operation_type = last.operation_type
        rework_minutes = max(30, round(last.processing_minutes * rejected / order.quantity))
    generator_capacity = request.generator_capacity_kw
    if generator_capacity is None:
        generator_capacity = max(
            180.0,
            max((window.generator_capacity_kw for window in problem.power_windows), default=0.0),
        )
    return DisruptionEvent(
        kind=kind,
        start_at=request.start,
        end_at=end_at,
        machine_id=machine_id,
        operator_id=operator_id,
        order_id=order_id,
        generator_available=request.generator_available,
        generator_capacity_kw=generator_capacity,
        rejected_quantity=rejected,
        operation_type=operation_type,
        rework_minutes=rework_minutes,
        description=request.notes,
    )


def _change_time(moment: datetime | None, shift: str | None, machine: str | None) -> str:
    if moment is None:
        return "Not scheduled"
    return f"{moment:%d %b %H:%M} · {shift or 'N/A'} · {machine or 'N/A'}"


def _change_impact(change: Any) -> str:
    if change.change_type == "ADDED":
        return "Recovery work added"
    if change.change_type == "UNSCHEDULED":
        return "Capacity conflict"
    if change.old_machine_id != change.new_machine_id:
        return f"{change.old_machine_id} → {change.new_machine_id}"
    if change.old_shift != change.new_shift:
        return f"{change.old_shift} → {change.new_shift}"
    if change.old_start and change.new_start:
        hours = (change.new_start - change.old_start).total_seconds() / 3_600
        return f"{hours:+.1f} h start movement"
    return change.change_type.title()


def _lost_output(result: ReplanResult) -> int:
    event = result.disruption
    if not event.end_at:
        return 0
    total = 0.0
    for task in result.previous_schedule.tasks:
        resource_match = (
            event.kind == DisruptionKind.MACHINE_BREAKDOWN
            and task.machine_id == event.machine_id
        ) or (
            event.kind == DisruptionKind.OPERATOR_ABSENCE
            and task.operator_id == event.operator_id
        )
        if not resource_match:
            continue
        left, right = max(task.start, event.start_at), min(task.end, event.end_at)
        if right > left:
            fraction = (right - left).total_seconds() / max(
                1.0, (task.end - task.start).total_seconds()
            )
            total += task.quantity * fraction
    return max(0, round(total))


def _owner_call(result: ReplanResult) -> dict[str, str]:
    event = result.disruption
    cost = result.difference.cost_impact["total_disruption_cost"]
    risk = ", ".join(result.difference.deliveries_now_at_risk) or "current promises"
    contacts = {
        DisruptionKind.MACHINE_BREAKDOWN: "Maintenance lead and approved repair contractor",
        DisruptionKind.OPERATOR_ABSENCE: "Shift supervisor and workforce coordinator",
        DisruptionKind.MATERIAL_DELAY: "Material supplier and customer planning desk",
        DisruptionKind.QUALITY_FAILURE: "Quality lead and production supervisor",
        DisruptionKind.POWER_CUT: "Utility control room and generator contractor",
    }
    return {
        "contact": contacts[event.kind],
        "reason": (
            f"Confirm the recovery action protecting {risk}; the validated replan "
            f"models ₹{cost:,.0f} total disruption impact."
        ),
    }


def _replan_payload(problem: PlanningProblem, result: ReplanResult) -> dict[str, Any]:
    difference = result.difference
    schedule = result.revised_schedule
    changes = []
    for change in difference.changes:
        operation = result.revised_problem.operation_map.get(change.operation_id) or problem.operation_map.get(change.operation_id)
        changes.append(
            {
                "order": change.order_id,
                "operation": operation.operation_type if operation else change.operation_id,
                "before": _change_time(
                    change.old_start, change.old_shift, change.old_machine_id
                ),
                "after": _change_time(
                    change.new_start, change.new_shift, change.new_machine_id
                ),
                "impact": _change_impact(change),
            }
        )
    cost = difference.cost_impact
    return {
        "disruptionCost": cost["total_disruption_cost"],
        "jobsMoved": difference.jobs_moved,
        "machineChanges": difference.machine_changes,
        "shiftChanges": difference.shift_changes,
        "newOvertimeHours": round(difference.new_overtime_minutes / 60, 1),
        "newGeneratorHours": round(difference.new_generator_minutes / 60, 1),
        "ordersAtRisk": difference.deliveries_now_at_risk,
        "penaltyIncrease": cost["penalty_increase"],
        "lostProduction": _lost_output(result),
        "ownerCall": _owner_call(result),
        "changes": changes,
        "explanation": result.explanation,
        "difference": _camel(difference.as_dict()),
        "frozenTaskIds": list(result.frozen_task_ids),
        "solver": _value(schedule.solver),
        "status": _value(schedule.status),
        "valid": schedule.valid,
        "violations": _violations(schedule),
        "diagnostics": list(schedule.diagnostics),
        "solverPolicy": _solver_policy(schedule, requested_exact=False),
        "revisedSchedule": _schedule_payload(
            result.revised_problem, schedule, requested_exact=False
        ),
    }


def _run_replan(request: DisruptionRequest, db: Session) -> dict[str, Any]:
    problem, _ = _load_problem(db)
    mode = _mode(request.mode)
    engine = _engine(exact=False)
    baseline = engine.generate(problem, mode)
    event = _disruption_event(request, problem)
    try:
        result = ReplanningService(engine).replan(problem, baseline, event, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _replan_payload(problem, result)


@router.post("/disruptions")
def inject_disruption(
    request: DisruptionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return _run_replan(request, db)


@router.post("/schedule/replan")
def replan_schedule(
    request: DisruptionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    return _run_replan(request, db)


def _scenario_label(value: str) -> str:
    return value.replace("_", "-").replace("-", " ").title()


def _factory_utilization(
    problem: PlanningProblem, schedule: ScheduleResult
) -> float:
    capacity = calculate_machine_capacity(problem, schedule)
    available = sum(item.available_minutes for item in capacity)
    committed = sum(item.committed_minutes for item in capacity)
    return round(100 * committed / available, 1) if available else 0.0


def _grinder(problem: PlanningProblem) -> Machine:
    machine = next(
        (
            item
            for item in problem.machines
            if "GRINDING" in {str(capability).upper() for capability in item.capabilities}
        ),
        None,
    )
    if machine is None:
        raise HTTPException(status_code=422, detail="No grinding-capable machine is configured")
    return machine


def _simulation_problem(
    problem: PlanningProblem, scenario: str, magnitude: float
) -> tuple[PlanningProblem, str]:
    if scenario == "operator-absence":
        grinder = _grinder(problem)
        qualified = [
            operator
            for operator in problem.operators
            if operator.is_qualified(grinder, "GRINDING")
        ]
        absent_ids = {
            operator.id for operator in qualified[: max(1, min(len(qualified), round(magnitude)))]
        }
        operators = tuple(
            replace(operator, status="ABSENT")
            if operator.id in absent_ids
            else operator
            for operator in problem.operators
        )
        return replace(problem, operators=operators), f"Removed {len(absent_ids)} qualified grinder operator(s)."

    if scenario == "quantity-increase":
        target = problem.order_map.get("ORD-018") or max(
            problem.orders, key=lambda item: (item.priority, item.selling_price)
        )
        factor = 1 + magnitude * 0.10
        orders = tuple(
            replace(
                order,
                quantity=max(1, round(order.quantity * factor)),
                selling_price=round(order.selling_price * factor, 2),
                material_cost=round(order.material_cost * factor, 2),
                operations=tuple(
                    replace(
                        operation,
                        processing_minutes=max(1, round(operation.processing_minutes * factor)),
                        quantity=max(1, round(operation.quantity * factor)),
                    )
                    for operation in order.operations
                ),
            )
            if order.id == target.id
            else order
            for order in problem.orders
        )
        return replace(problem, orders=orders), f"Increased {target.id} quantity by {(factor - 1) * 100:.0f}%."

    if scenario == "sunday-overtime":
        day = problem.horizon_start.date()
        while day.weekday() != 6:
            day += timedelta(days=1)
        start_at = datetime.combine(day, time(14))
        end_at = min(problem.horizon_end, start_at + timedelta(hours=magnitude))
        extra = CalendarWindow(
            start_at, end_at, "SCENARIO-SUNDAY-OT", is_overtime=True, is_sunday=True
        )
        operators = tuple(
            replace(operator, availability=(*operator.availability, extra))
            if operator.overtime_eligible
            else operator
            for operator in problem.operators
        )
        return (
            replace(problem, shifts=(*problem.shifts, extra), operators=operators),
            f"Added {magnitude:.1f} Sunday overtime hours with qualified labour.",
        )

    if scenario == "new-grinder":
        source = _grinder(problem)
        additions = tuple(
            replace(
                source,
                id=f"GRIND-SCENARIO-{index + 1:02d}",
                health_score=98.0,
                failure_probability=0.01,
                unavailable=(),
                status="IDLE",
            )
            for index in range(max(1, min(2, round(magnitude))))
        )
        addition_ids = {machine.id for machine in additions}
        operators = tuple(
            replace(
                operator,
                qualified_machine_ids=frozenset(
                    (*operator.qualified_machine_ids, source.id, *addition_ids)
                ),
            )
            if operator.is_qualified(source, "GRINDING")
            else operator
            for operator in problem.operators
        )
        orders = tuple(
            replace(
                order,
                operations=tuple(
                    replace(
                        operation,
                        eligible_machine_ids=frozenset(
                            (*operation.eligible_machine_ids, *addition_ids)
                        ),
                    )
                    if operation.operation_type.upper() == "GRINDING"
                    else operation
                    for operation in order.operations
                ),
            )
            for order in problem.orders
        )
        return (
            replace(
                problem,
                machines=(*problem.machines, *additions),
                operators=operators,
                orders=orders,
            ),
            f"Added {len(additions)} grinding machine(s) with the existing qualified operator pool.",
        )

    if scenario == "cross-train":
        grinder = _grinder(problem)
        candidates = [
            operator
            for operator in problem.operators
            if not operator.is_qualified(grinder, "GRINDING")
            and str(operator.status).upper() in {"AVAILABLE", "PRESENT", "ACTIVE"}
        ]
        trained_ids = {
            operator.id for operator in candidates[: max(1, min(len(candidates), round(magnitude)))]
        }
        operators = tuple(
            replace(
                operator,
                skills=frozenset((*operator.skills, "GRINDING")),
                qualified_machine_ids=frozenset(
                    (*operator.qualified_machine_ids, grinder.id)
                ),
                qualified_machine_types=frozenset(
                    (*operator.qualified_machine_types, grinder.machine_type)
                ),
            )
            if operator.id in trained_ids
            else operator
            for operator in problem.operators
        )
        return replace(problem, operators=operators), f"Cross-trained {len(trained_ids)} operator(s) for grinding."

    if scenario == "outsource":
        grinder = _grinder(problem)
        vendor_machine = replace(
            grinder,
            id="OUTSOURCE-GRIND",
            power_kw=0.0,
            hourly_cost=problem.costs.outsourcing_cost_per_hour,
            health_score=100.0,
            failure_probability=0.0,
            unavailable=(),
            status="IDLE",
        )
        vendor_windows = tuple(
            window
            for window in problem.shifts
            if (window.end - window.start).total_seconds() / 3_600 <= max(1.0, magnitude)
            or not window.is_overtime
        )
        vendor = Operator(
            id="VENDOR-GRIND",
            skills=frozenset({"GRINDING"}),
            qualified_machine_ids=frozenset({vendor_machine.id}),
            qualified_machine_types=frozenset({vendor_machine.machine_type}),
            availability=vendor_windows,
            overtime_eligible=True,
            status="AVAILABLE",
        )
        return (
            replace(
                problem,
                machines=(*problem.machines, vendor_machine),
                operators=(*problem.operators, vendor),
                metadata={
                    **problem.metadata,
                    "outsourcing_cost": magnitude
                    * problem.costs.outsourcing_cost_per_hour,
                },
            ),
            f"Added an approved outsourced grinding lane for up to {magnitude:.1f} hours.",
        )
    raise HTTPException(status_code=422, detail=f"Unsupported scenario {scenario!r}")


@router.post("/simulation/run")
def run_simulation(
    request: SimulationRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    problem, _ = _load_problem(db)
    scenario = request.scenario.strip().lower().replace("_", "-").replace(" ", "-")
    supported = {
        "grinder-breakdown",
        "operator-absence",
        "power-failure",
        "quantity-increase",
        "sunday-overtime",
        "new-grinder",
        "cross-train",
        "outsource",
    }
    if scenario not in supported:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported scenario; use {', '.join(sorted(supported))}",
        )
    engine = _engine(exact=False)
    baseline = engine.generate(problem, ScheduleMode.MOST_ROBUST)
    explanation: str
    scenario_problem: PlanningProblem
    scenario_schedule: ScheduleResult

    if scenario in {"grinder-breakdown", "power-failure"}:
        start_at = problem.horizon_start + timedelta(days=1, hours=5)
        if scenario == "grinder-breakdown":
            grinder = _grinder(problem)
            event = DisruptionEvent(
                kind=DisruptionKind.MACHINE_BREAKDOWN,
                start_at=start_at,
                end_at=min(
                    problem.horizon_end,
                    start_at + timedelta(hours=request.magnitude),
                ),
                machine_id=grinder.id,
                description="What-if grinding outage",
            )
        else:
            event = DisruptionEvent(
                kind=DisruptionKind.POWER_CUT,
                start_at=start_at,
                end_at=min(
                    problem.horizon_end,
                    start_at + timedelta(hours=request.magnitude),
                ),
                generator_available=True,
                generator_capacity_kw=180.0,
                description="What-if grid outage",
            )
        simulated = ScenarioSimulator(engine).run(
            _scenario_label(scenario),
            problem,
            baseline,
            event,
            mode=ScheduleMode.MOST_ROBUST,
            iterations=80,
            seed=42,
        )
        scenario_problem = simulated.replan.revised_problem
        scenario_schedule = simulated.replan.revised_schedule
        explanation = simulated.replan.explanation
    else:
        scenario_problem, explanation = _simulation_problem(
            problem, scenario, request.magnitude
        )
        scenario_schedule = engine.generate(
            scenario_problem, ScheduleMode.MOST_ROBUST
        )

    baseline_financial = calculate_schedule_financials(problem, baseline)
    financial = calculate_schedule_financials(scenario_problem, scenario_schedule)
    baseline_bottleneck = identify_bottleneck(problem, baseline)
    bottleneck = identify_bottleneck(scenario_problem, scenario_schedule)
    profit_delta = financial.expected_profit - baseline_financial.expected_profit
    delivery_delta = (
        financial.on_time_delivery_pct - baseline_financial.on_time_delivery_pct
    )
    if not scenario_schedule.valid:
        recommendation = (
            f"Do not implement this scenario as modeled. {explanation} The resulting "
            "schedule is not fully feasible; resolve the reported capacity violations first."
        )
    elif profit_delta >= 0 and delivery_delta >= 0:
        recommendation = (
            f"Proceed if the operating assumptions are approved. {explanation} It improves "
            f"expected profit by ₹{profit_delta:,.0f} without reducing on-time delivery."
        )
    else:
        recommendation = (
            f"Use only as a targeted recovery option. {explanation} The modeled change is "
            f"{delivery_delta:+.1f} delivery points and ₹{profit_delta:+,.0f} expected profit."
        )
    return {
        "label": _scenario_label(scenario),
        "delivery": financial.on_time_delivery_pct,
        "revenue": financial.revenue,
        "cost": financial.production_cost,
        "profit": financial.expected_profit,
        "penalties": financial.late_penalties,
        "overtime": financial.overtime_cost,
        "utilization": _factory_utilization(scenario_problem, scenario_schedule),
        "bottleneckLoad": bottleneck.utilization_pct,
        "recommendation": recommendation,
        "baseline": {
            "delivery": baseline_financial.on_time_delivery_pct,
            "revenue": baseline_financial.revenue,
            "cost": baseline_financial.production_cost,
            "profit": baseline_financial.expected_profit,
            "penalties": baseline_financial.late_penalties,
            "overtime": baseline_financial.overtime_cost,
            "utilization": _factory_utilization(problem, baseline),
            "bottleneckLoad": baseline_bottleneck.utilization_pct,
        },
        "solver": _value(scenario_schedule.solver),
        "status": _value(scenario_schedule.status),
        "valid": scenario_schedule.valid,
        "violations": _violations(scenario_schedule),
        "diagnostics": list(scenario_schedule.diagnostics),
        "solverPolicy": _solver_policy(
            scenario_schedule, requested_exact=False
        ),
    }


@router.get("/analytics/profitability")
@router.get("/analytics/profitability-live", include_in_schema=False)
def live_profitability(db: Session = Depends(get_db)) -> dict[str, Any]:
    problem, _ = _load_problem(db)
    result = _engine(exact=False).generate(problem, ScheduleMode.MOST_ON_TIME)
    financial = calculate_schedule_financials(problem, result)
    metrics = financial.as_dict()
    metrics.pop("by_order", None)
    return {
        **_camel(metrics),
        "solver": _value(result.solver),
        "status": _value(result.status),
        "valid": result.valid,
        "violations": _violations(result),
        "solverPolicy": _solver_policy(result, requested_exact=False),
    }


@router.get("/schedule/comparison")
@router.get("/schedule/comparison/live", include_in_schema=False)
def live_schedule_comparison(db: Session = Depends(get_db)) -> dict[str, Any]:
    problem, _ = _load_problem(db)
    comparison = compare_modes(problem, _engine(exact=False))
    plans = []
    for row in comparison.rows:
        result = comparison.results[row.mode]
        exposure_level = (
            "HIGH"
            if row.breakdown_exposure >= 560_000
            else "MEDIUM"
            if row.breakdown_exposure >= 450_000
            else "LOW"
        )
        plans.append(
            {
                "mode": row.mode,
                "name": row.mode.replace("_", " ").title(),
                "feasible": row.feasible,
                "isValid": row.valid,
                "productionCost": row.production_cost,
                "expectedProfit": row.expected_profit,
                "overtimeCost": row.overtime_cost,
                "latePenalties": row.penalties,
                "generatorCost": row.generator_cost,
                "onTimeDeliveryPercent": row.on_time_delivery_pct,
                "changeoverCost": row.changeover_cost,
                "breakdownExposure": exposure_level,
                "breakdownExposureCost": row.breakdown_exposure,
                "solver": _value(result.solver),
                "status": _value(result.status),
                "violations": _violations(result),
            }
        )
    return {
        "plans": plans,
        "recommendedMode": comparison.recommended_mode,
        "explanation": comparison.explanation,
        "solverPolicy": {
            "requestedExact": False,
            "usedFallback": False,
            "explanation": (
                "All three live modes use the deterministic validated heuristic "
                "to keep the comparison interactive."
            ),
        },
    }
