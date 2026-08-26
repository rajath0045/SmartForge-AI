from __future__ import annotations

from datetime import date, time

from app.core.enums import MachineType, OperationType, ResourceStatus

from .common import ORMModel


class ShiftRead(ORMModel):
    id: str
    name: str
    start_time: time
    end_time: time
    capacity_hours: float
    is_overtime: bool
    labour_multiplier: float


class OperatorSkillRead(ORMModel):
    id: int
    operation_type: OperationType
    machine_type: MachineType
    proficiency: int
    certified: bool
    certification_expires_on: date | None


class OperatorRead(ORMModel):
    id: str
    employee_code: str
    name: str
    status: ResourceStatus
    experience_years: float
    overtime_eligible: bool
    max_overtime_hours_week: float
    hourly_rate: float
    is_active: bool
    shift: ShiftRead
    skills: list[OperatorSkillRead]
