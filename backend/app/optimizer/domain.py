"""Pure planning-domain types used by the optimizer and decision services.

The database is deliberately kept out of the optimization core.  API code can
construct these dataclasses from SQLAlchemy rows, while tests and simulations
can create them directly.  This makes a schedule reproducible and avoids a
solver holding an open database session.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from math import ceil
from typing import Any, Iterable, Mapping, Sequence

try:  # Keep this module usable in isolation during optimization tests.
    from app.core.enums import ScheduleMode
except ImportError:  # pragma: no cover - only used outside the application package
    class ScheduleMode(StrEnum):
        CHEAPEST = "CHEAPEST"
        MOST_ON_TIME = "MOST_ON_TIME"
        MOST_ROBUST = "MOST_ROBUST"


class SolverKind(StrEnum):
    CP_SAT = "CP_SAT"
    HEURISTIC = "HEURISTIC"


class ScheduleSolveStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True, slots=True)
class CalendarWindow:
    start: datetime
    end: datetime
    name: str = "SHIFT"
    is_overtime: bool = False
    is_sunday: bool = False

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("calendar window end must be after start")


@dataclass(frozen=True, slots=True)
class PowerWindow:
    start: datetime
    end: datetime
    grid_available: bool = True
    generator_available: bool = False
    generator_capacity_kw: float = 0.0
    grid_cost_per_kwh: float | None = None
    generator_cost_per_kwh: float | None = None
    name: str = "POWER"

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("power window end must be after start")


@dataclass(frozen=True, slots=True)
class ChangeoverRule:
    from_family: str
    to_family: str
    minutes: int
    cost: float = 0.0
    machine_type: str | None = None


@dataclass(frozen=True, slots=True)
class Machine:
    id: str
    machine_type: str
    capabilities: frozenset[str]
    power_kw: float = 0.0
    hourly_cost: float = 0.0
    health_score: float = 100.0
    failure_probability: float = 0.0
    unavailable: tuple[CalendarWindow, ...] = ()
    status: str = "IDLE"

    def can_process(self, operation_type: str) -> bool:
        return _norm(operation_type) in {_norm(item) for item in self.capabilities}


@dataclass(frozen=True, slots=True)
class Operator:
    id: str
    skills: frozenset[str]
    qualified_machine_ids: frozenset[str] = frozenset()
    qualified_machine_types: frozenset[str] = frozenset()
    availability: tuple[CalendarWindow, ...] = ()
    overtime_eligible: bool = True
    max_overtime_minutes: int | None = None
    status: str = "AVAILABLE"

    def is_qualified(self, machine: Machine, required_skill: str) -> bool:
        normalized_skills = {_norm(item) for item in self.skills}
        has_skill = _norm(required_skill) in normalized_skills
        if not has_skill:
            return False
        if self.qualified_machine_ids and machine.id not in self.qualified_machine_ids:
            return False
        if self.qualified_machine_types and _norm(machine.machine_type) not in {
            _norm(item) for item in self.qualified_machine_types
        }:
            return False
        return _norm(self.status) in {"AVAILABLE", "PRESENT", "ACTIVE"}


@dataclass(frozen=True, slots=True)
class Operation:
    id: str
    order_id: str
    sequence: int
    operation_type: str
    processing_minutes: int
    required_skill: str | None = None
    eligible_machine_ids: frozenset[str] = frozenset()
    predecessor_ids: tuple[str, ...] = ()
    setup_minutes: int = 0
    quantity: int = 0

    def __post_init__(self) -> None:
        if self.processing_minutes <= 0:
            raise ValueError(f"operation {self.id} processing_minutes must be positive")
        if self.setup_minutes < 0:
            raise ValueError(f"operation {self.id} setup_minutes cannot be negative")

    @property
    def skill(self) -> str:
        return self.required_skill or self.operation_type

    @property
    def duration_minutes(self) -> int:
        return self.setup_minutes + self.processing_minutes


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    customer_id: str
    customer_tier: str
    part_family: str
    quantity: int
    due_at: datetime
    operations: tuple[Operation, ...]
    release_at: datetime | None = None
    selling_price: float = 0.0
    material_cost: float = 0.0
    late_penalty_per_day: float = 0.0
    strategic_weight: float = 1.0
    priority: int = 1
    quality_reject_rate: float = 0.0
    status: str = "PLANNED"

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"order {self.id} quantity must be positive")
        operation_ids = [operation.id for operation in self.operations]
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError(f"order {self.id} has duplicate operation ids")


@dataclass(frozen=True, slots=True)
class CostConfig:
    regular_labour_per_hour: float = 280.0
    overtime_multiplier: float = 1.75
    sunday_multiplier: float = 2.0
    grid_cost_per_kwh: float = 9.0
    generator_cost_per_kwh: float = 28.0
    changeover_labour_per_hour: float = 280.0
    rework_cost_per_unit: float = 120.0
    outsourcing_cost_per_hour: float = 2_500.0
    robust_buffer_ratio: float = 0.12
    objective_scale: int = 100


@dataclass(frozen=True, slots=True)
class ScheduleTask:
    id: str
    operation_id: str
    order_id: str
    machine_id: str
    operator_id: str
    start: datetime
    end: datetime
    shift_name: str
    part_family: str
    operation_type: str
    quantity: int = 0
    is_overtime: bool = False
    is_sunday: bool = False
    uses_generator: bool = False
    changeover_minutes: int = 0
    changeover_cost: float = 0.0
    status: str = "PLANNED"
    is_frozen: bool = False
    robust_buffer_minutes: int = 0

    @property
    def duration_minutes(self) -> int:
        return max(0, round((self.end - self.start).total_seconds() / 60))


@dataclass(slots=True)
class ScheduleResult:
    mode: ScheduleMode
    status: ScheduleSolveStatus
    solver: SolverKind
    tasks: list[ScheduleTask] = field(default_factory=list)
    objective_value: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)
    valid: bool = False
    violations: list[Any] = field(default_factory=list)
    generated_at: datetime | None = None

    @property
    def feasible(self) -> bool:
        return self.status in {ScheduleSolveStatus.OPTIMAL, ScheduleSolveStatus.FEASIBLE}


@dataclass(frozen=True, slots=True)
class PlanningProblem:
    horizon_start: datetime
    horizon_end: datetime
    machines: tuple[Machine, ...]
    operators: tuple[Operator, ...]
    orders: tuple[Order, ...]
    shifts: tuple[CalendarWindow, ...]
    power_windows: tuple[PowerWindow, ...] = ()
    changeovers: tuple[ChangeoverRule, ...] = ()
    costs: CostConfig = field(default_factory=CostConfig)
    allow_overtime: bool = True
    allow_generator: bool = True
    fixed_tasks: tuple[ScheduleTask, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.horizon_end <= self.horizon_start:
            raise ValueError("planning horizon end must be after start")
        if not self.machines:
            raise ValueError("at least one machine is required")
        if not self.operators:
            raise ValueError("at least one operator is required")
        if not self.shifts:
            raise ValueError("at least one shift window is required")

    @property
    def operation_map(self) -> dict[str, Operation]:
        return {
            operation.id: operation
            for order in self.orders
            for operation in order.operations
        }

    @property
    def order_map(self) -> dict[str, Order]:
        return {order.id: order for order in self.orders}

    @property
    def machine_map(self) -> dict[str, Machine]:
        return {machine.id: machine for machine in self.machines}

    @property
    def operator_map(self) -> dict[str, Operator]:
        return {operator.id: operator for operator in self.operators}

    def with_orders(self, orders: Iterable[Order]) -> "PlanningProblem":
        return replace(self, orders=tuple(orders))


def default_two_shift_calendar(
    horizon_start: datetime,
    horizon_end: datetime,
    *,
    include_sundays: bool = False,
    include_overtime: bool = True,
) -> tuple[CalendarWindow, ...]:
    """Create a deterministic two-shift calendar (06:00-14:00, 14:00-22:00).

    An optional 22:00-02:00 recovery window is marked as overtime.  Sunday
    regular shifts are excluded by default but a Sunday overtime window can be
    used when explicitly enabled by a schedule mode/problem configuration.
    """

    windows: list[CalendarWindow] = []
    day = horizon_start.date()
    last_day = horizon_end.date()
    while day <= last_day:
        sunday = day.weekday() == 6
        if include_sundays or not sunday:
            for name, start_time, end_time in (
                ("SHIFT_1", time(6), time(14)),
                ("SHIFT_2", time(14), time(22)),
            ):
                start = datetime.combine(day, start_time, tzinfo=horizon_start.tzinfo)
                end = datetime.combine(day, end_time, tzinfo=horizon_start.tzinfo)
                if end > horizon_start and start < horizon_end:
                    windows.append(
                        CalendarWindow(max(start, horizon_start), min(end, horizon_end), name, False, sunday)
                    )
        if include_overtime:
            start = datetime.combine(day, time(22), tzinfo=horizon_start.tzinfo)
            end = datetime.combine(day + timedelta(days=1), time(2), tzinfo=horizon_start.tzinfo)
            if end > horizon_start and start < horizon_end:
                windows.append(
                    CalendarWindow(
                        max(start, horizon_start),
                        min(end, horizon_end),
                        "OVERTIME",
                        True,
                        sunday,
                    )
                )
        day += timedelta(days=1)
    return tuple(windows)


def changeover_for(
    problem: PlanningProblem,
    machine: Machine,
    from_family: str,
    to_family: str,
) -> tuple[int, float]:
    """Return the configured setup transition, with manufacturing defaults.

    Exact matrix entries win.  A same-family transition defaults to 20 minutes,
    a related-prefix transition to 60 minutes, and an unrelated family to 180.
    """

    for rule in problem.changeovers:
        if (
            _norm(rule.from_family) == _norm(from_family)
            and _norm(rule.to_family) == _norm(to_family)
            and (rule.machine_type is None or _norm(rule.machine_type) == _norm(machine.machine_type))
        ):
            return max(0, int(rule.minutes)), max(0.0, float(rule.cost))
    if _norm(from_family) == _norm(to_family):
        return 20, 0.0
    if _family_group(from_family) == _family_group(to_family):
        return 60, 0.0
    return 180, 0.0


def problem_from_records(
    *,
    horizon_start: datetime,
    horizon_end: datetime,
    machines: Sequence[Any],
    operators: Sequence[Any],
    orders: Sequence[Any],
    shifts: Sequence[Any] | None = None,
    power_windows: Sequence[Any] = (),
    changeovers: Sequence[Any] = (),
    costs: CostConfig | Mapping[str, Any] | Any | None = None,
    allow_overtime: bool = True,
    allow_generator: bool = True,
    fixed_tasks: Sequence[Any] = (),
) -> PlanningProblem:
    """Tolerantly adapt dictionaries, Pydantic models, or ORM rows.

    The adapter intentionally accepts the normalized model field names used by
    the backend as well as compact names useful for scenario fixtures.
    """

    adapted_machines = tuple(_adapt_machine(row) for row in machines)
    adapted_shifts = tuple(
        window
        for row in shifts or ()
        for window in _expand_calendar_record(row, horizon_start, horizon_end)
    )
    if not adapted_shifts:
        adapted_shifts = default_two_shift_calendar(horizon_start, horizon_end)
    adapted_operators = tuple(
        _adapt_operator(
            row,
            horizon_start,
            horizon_end,
            all_shift_windows=adapted_shifts,
        )
        for row in operators
    )
    adapted_orders = tuple(_adapt_order(row) for row in orders)
    adapted_power = tuple(_adapt_power_window(row) for row in power_windows)
    adapted_changeovers = tuple(_adapt_changeover(row) for row in changeovers)
    adapted_fixed = tuple(_adapt_task(row) for row in fixed_tasks)
    adapted_costs = costs if isinstance(costs, CostConfig) else _adapt_costs(costs)
    return PlanningProblem(
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        machines=adapted_machines,
        operators=adapted_operators,
        orders=adapted_orders,
        shifts=adapted_shifts,
        power_windows=adapted_power,
        changeovers=adapted_changeovers,
        costs=adapted_costs,
        allow_overtime=allow_overtime,
        allow_generator=allow_generator,
        fixed_tasks=adapted_fixed,
    )


def order_from_record(row: Any) -> Order:
    """Adapt one ProductionOrder/RFQ mapping, Pydantic model, or ORM row."""

    return _adapt_order(row)


def schedule_tasks_from_records(rows: Sequence[Any]) -> tuple[ScheduleTask, ...]:
    """Adapt persisted ScheduleOperation rows for validation/replanning."""

    return tuple(_adapt_task(row) for row in rows)


def _adapt_machine(row: Any) -> Machine:
    capabilities = _value(row, "capabilities", default=())
    if capabilities and not isinstance(capabilities, (str, bytes)):
        capabilities = tuple(
            _value(item, "operation_type", default=item) for item in capabilities
        )
    windows = [
        *(_value(row, "unavailable", default=()) or ()),
        *(_value(row, "maintenance_windows", default=()) or ()),
        *(_value(row, "breakdowns", default=()) or ()),
    ]
    health = float(_value(row, "health_score", default=100.0) or 100.0)
    failure = _value(row, "failure_probability", default=None)
    if failure is None:
        failure = max(0.0, min(0.8, (100.0 - health) / 100.0))
    return Machine(
        id=str(_value(row, "id")),
        machine_type=str(_value(row, "machine_type", "type", default="UNKNOWN")),
        capabilities=frozenset(str(item) for item in capabilities),
        power_kw=float(_value(row, "power_kw", default=0.0) or 0.0),
        hourly_cost=float(_value(row, "hourly_cost", default=0.0) or 0.0),
        health_score=health,
        failure_probability=float(failure),
        unavailable=tuple(_adapt_calendar_window(item) for item in windows if _window_active(item)),
        status=str(_value(row, "status", default="IDLE")),
    )


def _adapt_operator(
    row: Any,
    horizon_start: datetime | None = None,
    horizon_end: datetime | None = None,
    all_shift_windows: tuple[CalendarWindow, ...] = (),
) -> Operator:
    skill_rows = _value(row, "skills", "operator_skills", default=()) or ()
    skills: list[str] = []
    machine_types: list[str] = []
    machine_ids: list[str] = list(_value(row, "qualified_machine_ids", default=()) or ())
    for item in skill_rows:
        if not bool(_value(item, "certified", default=True)):
            continue
        skills.append(str(_value(item, "operation_type", "skill", default=item)))
        machine_type = _value(item, "machine_type", default=None)
        if machine_type:
            machine_types.append(str(machine_type))
    availability = _value(row, "availability", "availability_windows", default=()) or ()
    adapted_availability: tuple[CalendarWindow, ...]
    if horizon_start is not None and horizon_end is not None:
        adapted_availability = _operator_availability_windows(
            row,
            availability,
            horizon_start,
            horizon_end,
            all_shift_windows,
        )
    else:
        adapted_availability = tuple(
            _adapt_calendar_window(item)
            for item in availability
            if _window_available(item)
        )
    max_overtime = _value(row, "max_overtime_minutes", default=None)
    if max_overtime is None:
        overtime_hours = _value(row, "max_overtime_hours_week", default=None)
        horizon_weeks = (
            max(1, ceil((horizon_end - horizon_start).total_seconds() / (7 * 86_400)))
            if horizon_start is not None and horizon_end is not None
            else 1
        )
        max_overtime = (
            None
            if overtime_hours is None
            else round(float(overtime_hours) * 60 * horizon_weeks)
        )
    return Operator(
        id=str(_value(row, "id")),
        skills=frozenset(skills),
        qualified_machine_ids=frozenset(str(item) for item in machine_ids),
        qualified_machine_types=frozenset(machine_types),
        availability=adapted_availability,
        overtime_eligible=bool(_value(row, "overtime_eligible", default=True)),
        max_overtime_minutes=_optional_int(max_overtime),
        status=str(_value(row, "status", default="AVAILABLE")),
    )


def _adapt_order(row: Any) -> Order:
    order_id = str(_value(row, "id"))
    quantity = int(_value(row, "quantity", default=1))
    raw_operations = _value(row, "operations", "order_operations", default=()) or ()
    operations: list[Operation] = []
    prior_id: str | None = None
    for index, item in enumerate(sorted(raw_operations, key=lambda op: int(_value(op, "sequence", default=0)))):
        operation_id = str(_value(item, "id", default=f"{order_id}-OP-{index + 1}"))
        run_per_unit = _value(item, "run_minutes_per_unit", default=None)
        explicit_duration = _value(item, "processing_minutes", "duration_minutes", default=None)
        setup = int(_value(item, "setup_minutes", default=0) or 0)
        if run_per_unit is not None:
            planned_quantity = int(
                _value(item, "planned_quantity", "quantity", default=quantity) or quantity
            )
            explicit_duration = float(run_per_unit) * planned_quantity
        elif explicit_duration is None:
            explicit_duration = quantity
        predecessor = _value(item, "predecessor_ids", default=None)
        predecessor_id = _value(item, "predecessor_id", default=None)
        if predecessor is None:
            predecessor = (str(predecessor_id),) if predecessor_id else ((prior_id,) if prior_id else ())
        eligible = _value(item, "eligible_machine_ids", default=None)
        if eligible is None:
            eligible = tuple(
                _value(entry, "machine_id", default=entry)
                for entry in (_value(item, "eligible_machines", default=()) or ())
            )
        operations.append(
            Operation(
                id=operation_id,
                order_id=order_id,
                sequence=int(_value(item, "sequence", default=index + 1)),
                operation_type=str(_value(item, "operation_type")),
                processing_minutes=max(1, ceil(float(explicit_duration))),
                required_skill=_optional_str(_value(item, "required_skill", default=None)),
                eligible_machine_ids=frozenset(str(machine_id) for machine_id in eligible),
                predecessor_ids=tuple(str(pred) for pred in predecessor if pred),
                setup_minutes=setup,
                quantity=int(_value(item, "quantity", default=quantity) or quantity),
            )
        )
        prior_id = operation_id
    customer = _value(row, "customer", default=None)
    tier = _value(row, "customer_tier", default=None)
    if tier is None and customer is not None:
        tier = _value(customer, "tier", default="TIER_2")
    strategic = _value(row, "strategic_weight", default=None)
    if strategic is None and customer is not None:
        strategic = _value(customer, "strategic_weight", default=1.0)
    family = _value(row, "part_family", default=None)
    if family is not None and not isinstance(family, str):
        family = _value(family, "id", "code", default=str(family))
    return Order(
        id=order_id,
        customer_id=str(_value(row, "customer_id", default=_value(customer, "id", default="UNKNOWN"))),
        customer_tier=str(tier or "TIER_2"),
        part_family=str(family or _value(row, "part_family_id", default="UNKNOWN")),
        quantity=quantity,
        due_at=_as_datetime(
            _value(row, "due_at", "due_date", "requested_delivery_date")
        ),
        operations=tuple(operations),
        release_at=_optional_datetime(
            _value(
                row,
                "release_at",
                "material_available_at",
                "material_available_date",
                "material_expected_at",
                default=None,
            )
        ),
        selling_price=float(_value(row, "selling_price", "revenue", default=0.0) or 0.0),
        material_cost=float(
            _value(
                row,
                "material_cost",
                "total_material_cost",
                default=(
                    float(_value(row, "material_required_qty", default=0.0) or 0.0)
                    * float(
                        _value(
                            _value(row, "material", default=None),
                            "unit_cost",
                            default=0.0,
                        )
                        or 0.0
                    )
                ),
            )
            or 0.0
        ),
        late_penalty_per_day=float(_value(row, "late_penalty_per_day", default=0.0) or 0.0),
        strategic_weight=float(strategic or 1.0),
        priority=int(_value(row, "priority", default=1) or 1),
        quality_reject_rate=float(_value(row, "quality_reject_rate", default=0.0) or 0.0),
        status=str(_value(row, "status", default="PLANNED")),
    )


def _adapt_calendar_window(row: Any) -> CalendarWindow:
    start = _as_datetime(_value(row, "start", "start_at"))
    raw_end = _value(row, "end", "end_at", default=None)
    end = _as_datetime(raw_end) if raw_end is not None else start + timedelta(days=365)
    return CalendarWindow(
        start=start,
        end=end,
        name=str(_value(row, "name", "shift_name", "type", default="WINDOW")),
        is_overtime=bool(_value(row, "is_overtime", default=False)),
        is_sunday=bool(_value(row, "is_sunday", default=False)),
    )


def _adapt_power_window(row: Any) -> PowerWindow:
    return PowerWindow(
        start=_as_datetime(_value(row, "start", "start_at")),
        end=_as_datetime(_value(row, "end", "end_at")),
        grid_available=bool(_value(row, "grid_available", default=True)),
        generator_available=bool(_value(row, "generator_available", default=False)),
        generator_capacity_kw=float(_value(row, "generator_capacity_kw", default=0.0) or 0.0),
        grid_cost_per_kwh=_optional_float(_value(row, "grid_cost_per_kwh", "electricity_cost_per_kwh", default=None)),
        generator_cost_per_kwh=_optional_float(_value(row, "generator_cost_per_kwh", default=None)),
        name=str(_value(row, "name", "event_type", default="POWER")),
    )


def _adapt_changeover(row: Any) -> ChangeoverRule:
    return ChangeoverRule(
        from_family=str(
            _value(row, "from_family", "from_family_id", "from_part_family_id")
        ),
        to_family=str(
            _value(row, "to_family", "to_family_id", "to_part_family_id")
        ),
        minutes=int(_value(row, "minutes", "changeover_minutes", default=0) or 0),
        cost=float(_value(row, "cost", "changeover_cost", default=0.0) or 0.0),
        machine_type=_optional_str(_value(row, "machine_type", default=None)),
    )


def _adapt_task(row: Any) -> ScheduleTask:
    start = _as_datetime(_value(row, "start", "start_at"))
    end = _as_datetime(_value(row, "end", "end_at"))
    order_operation = _value(row, "order_operation", default=None)
    order = _value(order_operation, "order", default=None)
    part_family = _value(order, "part_family", default=None)
    if part_family is not None and not isinstance(part_family, str):
        part_family = _value(part_family, "code", "id", default="UNKNOWN")
    return ScheduleTask(
        id=str(_value(row, "id")),
        operation_id=str(_value(row, "operation_id", "order_operation_id")),
        order_id=str(_value(row, "order_id", default=_value(order_operation, "order_id"))),
        machine_id=str(_value(row, "machine_id")),
        operator_id=str(_value(row, "operator_id")),
        start=start,
        end=end,
        shift_name=str(_value(row, "shift_name", "shift_id", default="SHIFT")),
        part_family=str(_value(row, "part_family", default=part_family or "UNKNOWN")),
        operation_type=str(
            _value(
                row,
                "operation_type",
                default=_value(order_operation, "operation_type", default="UNKNOWN"),
            )
        ),
        quantity=int(_value(row, "quantity", default=0) or 0),
        is_overtime=bool(_value(row, "is_overtime", default=False)),
        is_sunday=bool(_value(row, "is_sunday", default=start.weekday() == 6)),
        uses_generator=bool(_value(row, "uses_generator", default=False)),
        changeover_minutes=int(_value(row, "changeover_minutes", default=0) or 0),
        changeover_cost=float(_value(row, "changeover_cost", default=0.0) or 0.0),
        status=str(_value(row, "status", default="PLANNED")),
        is_frozen=bool(_value(row, "is_frozen", default=True)),
        robust_buffer_minutes=int(_value(row, "robust_buffer_minutes", default=0) or 0),
    )


def _expand_calendar_record(
    row: Any,
    horizon_start: datetime,
    horizon_end: datetime,
) -> tuple[CalendarWindow, ...]:
    """Expand either a concrete window or a recurring ORM Shift row."""

    if _value(row, "start", "start_at", default=None) is not None:
        return (_adapt_calendar_window(row),)
    start_time = _value(row, "start_time", default=None)
    end_time = _value(row, "end_time", default=None)
    if not isinstance(start_time, time) or not isinstance(end_time, time):
        raise TypeError(f"cannot adapt {row!r} as a calendar window or recurring shift")
    shift_id = str(_value(row, "id", "name", default="SHIFT"))
    day_of_week = _value(row, "day_of_week", default=None)
    is_overtime = bool(_value(row, "is_overtime", default=False))
    is_sunday = bool(_value(row, "is_sunday", default=False))
    windows: list[CalendarWindow] = []
    current = horizon_start.date()
    while current <= horizon_end.date():
        weekday_matches = day_of_week is None or int(day_of_week) == current.weekday()
        sunday_matches = (current.weekday() == 6) if is_sunday else (current.weekday() != 6)
        if weekday_matches and sunday_matches:
            start = datetime.combine(current, start_time, tzinfo=horizon_start.tzinfo)
            end_day = current + timedelta(days=1) if end_time <= start_time else current
            end = datetime.combine(end_day, end_time, tzinfo=horizon_start.tzinfo)
            clipped_start = max(start, horizon_start)
            clipped_end = min(end, horizon_end)
            if clipped_end > clipped_start:
                windows.append(
                    CalendarWindow(
                        clipped_start,
                        clipped_end,
                        shift_id,
                        is_overtime,
                        current.weekday() == 6,
                    )
                )
        current += timedelta(days=1)
    return tuple(windows)


def _operator_availability_windows(
    row: Any,
    availability_rows: Sequence[Any],
    horizon_start: datetime,
    horizon_end: datetime,
    all_shift_windows: tuple[CalendarWindow, ...],
) -> tuple[CalendarWindow, ...]:
    shift_id = str(_value(row, "shift_id", default=""))
    overtime_eligible = bool(_value(row, "overtime_eligible", default=True))
    if all_shift_windows:
        windows = [
            window
            for window in all_shift_windows
            if window.name == shift_id or (window.is_overtime and overtime_eligible)
        ]
    else:
        shift = _value(row, "shift", default=None)
        windows = (
            list(_expand_calendar_record(shift, horizon_start, horizon_end))
            if shift is not None
            else []
        )
    for record in availability_rows:
        if _value(record, "start", "start_at", default=None) is not None:
            concrete = _adapt_calendar_window(record)
            if _window_available(record):
                windows.append(concrete)
            else:
                windows = [
                    fragment
                    for window in windows
                    for fragment in _subtract_calendar(window, concrete.start, concrete.end)
                ]
            continue
        work_date = _value(record, "work_date", default=None)
        record_shift_id = str(_value(record, "shift_id", default=shift_id))
        if not isinstance(work_date, date):
            continue
        affected = [
            window
            for window in all_shift_windows
            if window.name == record_shift_id and window.start.date() == work_date
        ]
        if _window_available(record):
            available_hours = float(_value(record, "available_hours", default=8.0) or 0.0)
            for window in affected:
                end = min(window.end, window.start + timedelta(hours=available_hours))
                if end > window.start and not any(
                    existing.start == window.start and existing.end == end
                    for existing in windows
                ):
                    windows.append(replace(window, end=end))
        else:
            for unavailable in affected:
                windows = [
                    fragment
                    for window in windows
                    for fragment in _subtract_calendar(
                        window, unavailable.start, unavailable.end
                    )
                ]
    unique = {
        (window.start, window.end, window.name, window.is_overtime): window
        for window in windows
        if window.end > window.start
    }
    return tuple(sorted(unique.values(), key=lambda item: (item.start, item.name)))


def _subtract_calendar(
    window: CalendarWindow,
    unavailable_start: datetime,
    unavailable_end: datetime,
) -> tuple[CalendarWindow, ...]:
    if window.end <= unavailable_start or window.start >= unavailable_end:
        return (window,)
    fragments: list[CalendarWindow] = []
    if window.start < unavailable_start:
        fragments.append(replace(window, end=unavailable_start))
    if window.end > unavailable_end:
        fragments.append(replace(window, start=unavailable_end))
    return tuple(fragments)


def _adapt_costs(costs: Any) -> CostConfig:
    if costs is None:
        return CostConfig()
    if isinstance(costs, Mapping):
        raw = dict(costs)
    elif isinstance(costs, Sequence) and not isinstance(costs, (str, bytes)):
        raw = {
            str(_value(row, "key")): float(_value(row, "value", default=0.0))
            for row in costs
        }
    else:
        raw = _public_mapping(costs)
    aliases = {
        "regular_labour_rate": "regular_labour_per_hour",
        "electricity_price": "grid_cost_per_kwh",
        "generator_cost": "generator_cost_per_kwh",
        "changeover_labour_cost": "changeover_labour_per_hour",
        "rework_cost": "rework_cost_per_unit",
        "reserve_capacity_target": "robust_buffer_ratio",
    }
    valid_fields = set(CostConfig.__dataclass_fields__)
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        target = aliases.get(key, key)
        if target in valid_fields:
            normalized[target] = value
    return CostConfig(**normalized)


def _value(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _public_mapping(obj: Any) -> dict[str, Any]:
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return {key: value for key, value in vars(obj).items() if not key.startswith("_")}
    return {}


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.max.replace(microsecond=0))
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise TypeError(f"cannot convert {value!r} to datetime")


def _optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _as_datetime(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _window_active(row: Any) -> bool:
    return _norm(_value(row, "status", default="PLANNED")) not in {"CANCELLED", "COMPLETED"}


def _window_available(row: Any) -> bool:
    return _norm(_value(row, "status", default="AVAILABLE")) in {
        "AVAILABLE",
        "PRESENT",
        "ACTIVE",
        "PLANNED",
    }


def _norm(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw).strip().upper()


def _family_group(family: str) -> str:
    normalized = _norm(family)
    for separator in ("-", "_", "/"):
        if separator in normalized:
            return normalized.split(separator, 1)[0]
    return normalized[:2]


def minute_offset(moment: datetime, origin: datetime) -> int:
    return int(ceil((moment - origin).total_seconds() / 60))


def at_minute(origin: datetime, minute: int) -> datetime:
    return origin + timedelta(minutes=int(minute))
