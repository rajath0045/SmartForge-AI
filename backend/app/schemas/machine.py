from __future__ import annotations

from datetime import datetime

from app.core.enums import MachineStatus, MachineType, OperationType, WindowStatus

from .common import ORMModel


class MachineCapabilityRead(ORMModel):
    id: int
    operation_type: OperationType
    setup_minutes: int
    efficiency: float
    min_batch_size: int
    max_batch_size: int | None


class BreakdownRead(ORMModel):
    id: int
    start_at: datetime
    end_at: datetime | None
    reason: str
    failure_code: str | None
    lost_production_hours: float
    financial_impact: float
    status: WindowStatus


class MaintenanceRead(ORMModel):
    id: int
    start_at: datetime
    end_at: datetime
    maintenance_type: str
    status: WindowStatus
    estimated_cost: float
    notes: str | None
    is_mandatory: bool


class MachineSummary(ORMModel):
    id: str
    name: str
    machine_type: MachineType
    status: MachineStatus
    location: str
    power_kw: float
    hourly_cost: float
    total_running_hours: float
    health_score: float
    availability_rate: float
    performance_rate: float
    quality_rate: float
    oee: float
    mtbf_hours: float
    mttr_hours: float
    failure_count: int
    last_maintenance_at: datetime | None
    capabilities: list[MachineCapabilityRead]


class MachineDetail(MachineSummary):
    manufacturer: str | None
    model_number: str | None
    commissioned_year: int | None
    notes: str | None
    breakdowns: list[BreakdownRead]
    maintenance_windows: list[MaintenanceRead]
