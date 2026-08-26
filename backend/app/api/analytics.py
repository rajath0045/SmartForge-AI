from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from .metrics import capacity_snapshot

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _camel_capacity(snapshot: dict) -> dict:
    def row(item: dict) -> dict:
        return {
            "machineType": item.get("machine_type"),
            "machineCount": item.get("machine_count"),
            "availableHours": item.get("available_hours"),
            "committedHours": item.get("committed_hours"),
            "remainingHours": item.get("remaining_hours"),
            "utilizationPercent": item.get("utilization_percent"),
            "dependentOrders": item.get("dependent_orders"),
            "status": item.get("status"),
        }

    def machine_row(item: dict) -> dict:
        return {
            "machineId": item["machine_id"],
            "machineName": item["machine_name"],
            "machineType": item["machine_type"],
            "status": item["status"],
            "availableHours": item["available_hours"],
            "committedHours": item["committed_hours"],
            "remainingHours": item["remaining_hours"],
            "utilizationPercent": item["utilization_percent"],
            "healthScore": item["health_score"],
        }

    return {
        "horizonStart": snapshot["horizon_start"],
        "horizonEnd": snapshot["horizon_end"],
        "workingDays": snapshot["working_days"],
        "bottleneck": row(snapshot["bottleneck"]) if snapshot["bottleneck"] else None,
        "byMachineType": [row(item) for item in snapshot["by_machine_type"]],
        "byMachine": [machine_row(item) for item in snapshot["by_machine"]],
    }


@router.get("/capacity")
def get_capacity(db: Session = Depends(get_db)) -> dict:
    return _camel_capacity(capacity_snapshot(db))


@router.get("/bottlenecks")
def get_bottlenecks(db: Session = Depends(get_db)) -> dict:
    snapshot = _camel_capacity(capacity_snapshot(db))
    return {
        "currentBottleneck": snapshot["bottleneck"],
        "rankedResources": snapshot["byMachineType"],
    }
