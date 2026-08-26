from __future__ import annotations

from enum import StrEnum


class MachineStatus(StrEnum):
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    SETUP = "SETUP"
    MAINTENANCE = "MAINTENANCE"
    BREAKDOWN = "BREAKDOWN"


class MachineType(StrEnum):
    CNC_LATHE = "CNC_LATHE"
    MILLING = "MILLING"
    DRILLING = "DRILLING"
    GRINDING = "GRINDING"
    INSPECTION = "INSPECTION"


class OperationType(StrEnum):
    TURNING = "TURNING"
    MILLING = "MILLING"
    DRILLING = "DRILLING"
    GRINDING = "GRINDING"
    INSPECTION = "INSPECTION"
    REWORK = "REWORK"


class OrderStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    AT_RISK = "AT_RISK"
    DELAYED = "DELAYED"
    COMPLETED = "COMPLETED"


class CustomerTier(StrEnum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResourceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"
    TRAINING = "TRAINING"


class WindowStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ScheduleMode(StrEnum):
    CHEAPEST = "CHEAPEST"
    MOST_ON_TIME = "MOST_ON_TIME"
    MOST_ROBUST = "MOST_ROBUST"


class ScheduleStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class OperationStatus(StrEnum):
    PLANNED = "PLANNED"
    SETUP = "SETUP"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class DisruptionType(StrEnum):
    MACHINE_BREAKDOWN = "MACHINE_BREAKDOWN"
    OPERATOR_ABSENCE = "OPERATOR_ABSENCE"
    MATERIAL_DELAY = "MATERIAL_DELAY"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    POWER_CUT = "POWER_CUT"


class DisruptionStatus(StrEnum):
    OPEN = "OPEN"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"


class PowerEventType(StrEnum):
    NORMAL = "NORMAL"
    PLANNED_OUTAGE = "PLANNED_OUTAGE"
    UNPLANNED_OUTAGE = "UNPLANNED_OUTAGE"


class RFQStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPT = "ACCEPT"
    CONDITIONAL = "CONDITIONAL"
    NEGOTIATE = "NEGOTIATE"
    REJECT = "REJECT"


class RecommendationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"
    IMPLEMENTED = "IMPLEMENTED"
