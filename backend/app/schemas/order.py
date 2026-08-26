from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.core.enums import (
    CustomerTier,
    MachineType,
    OperationType,
    OrderStatus,
    RiskLevel,
)

from .common import ORMModel


class CustomerRead(ORMModel):
    id: str
    code: str
    name: str
    tier: CustomerTier
    strategic_weight: float


class PartFamilyRead(ORMModel):
    id: str
    code: str
    name: str
    fixture_code: str


class EligibleMachineRead(ORMModel):
    machine_id: str
    preference_rank: int


class OrderOperationRead(ORMModel):
    id: int
    sequence: int
    operation_type: OperationType
    required_machine_type: MachineType
    required_skill: OperationType
    setup_minutes: int
    run_minutes_per_unit: float
    batch_size: int
    planned_quantity: int
    predecessor_id: int | None
    outsource_allowed: bool
    processing_minutes: int
    eligible_machines: list[EligibleMachineRead]


class OrderSummary(ORMModel):
    id: str
    customer: CustomerRead
    part_family: PartFamilyRead
    part_number: str
    description: str
    quantity: int
    completed_quantity: int
    due_date: datetime
    promised_date: datetime | None
    status: OrderStatus
    risk_level: RiskLevel
    priority: int
    revenue: float
    expected_profit: float
    late_penalty_per_day: float
    delivery_probability: float
    expected_completion_at: datetime | None


class OrderDetail(OrderSummary):
    unit_selling_price: float
    unit_material_cost: float
    material_cost: float
    expected_production_cost: float
    material_id: str
    material_required_qty: float
    material_available_date: datetime
    quality_reject_rate: float
    notes: str | None
    operations: list[OrderOperationRead]


class OrderOperationCreate(ORMModel):
    operation_type: OperationType
    required_machine_type: MachineType
    setup_minutes: int = Field(default=30, ge=0, le=480)
    run_minutes_per_unit: float = Field(gt=0, le=240)
    batch_size: int = Field(default=1, ge=1)
    outsource_allowed: bool = False


class OrderCreate(ORMModel):
    customer_id: str
    part_family_id: str
    part_number: str = Field(min_length=2, max_length=50)
    description: str = Field(min_length=3, max_length=160)
    quantity: int = Field(ge=1, le=100_000)
    due_date: datetime
    priority: int = Field(default=3, ge=1, le=5)
    unit_selling_price: float = Field(gt=0)
    unit_material_cost: float = Field(ge=0)
    late_penalty_per_day: float = Field(ge=0)
    material_id: str
    material_required_qty: float = Field(gt=0)
    material_available_date: datetime
    quality_reject_rate: float = Field(default=0.03, ge=0, le=0.25)
    operations: list[OrderOperationCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates(self) -> OrderCreate:
        if self.material_available_date > self.due_date:
            raise ValueError("material availability cannot be after the due date")
        return self
