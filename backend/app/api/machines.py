from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import MachineStatus, MachineType
from app.models import Machine
from app.schemas.machine import MachineDetail, MachineSummary

router = APIRouter(prefix="/machines", tags=["machines"])


def _machine_options():
    return (
        selectinload(Machine.capabilities),
        selectinload(Machine.breakdowns),
        selectinload(Machine.maintenance_windows),
    )


@router.get("", response_model=list[MachineSummary])
def list_machines(
    status: MachineStatus | None = None,
    machine_type: MachineType | None = None,
    health_below: float | None = Query(default=None, ge=0, le=100),
    db: Session = Depends(get_db),
) -> list[Machine]:
    statement = select(Machine).options(*_machine_options()).order_by(Machine.id)
    if status is not None:
        statement = statement.where(Machine.status == status)
    if machine_type is not None:
        statement = statement.where(Machine.machine_type == machine_type)
    if health_below is not None:
        statement = statement.where(Machine.health_score < health_below)
    return list(db.scalars(statement).unique().all())


@router.get("/{machine_id}", response_model=MachineDetail)
def get_machine(machine_id: str, db: Session = Depends(get_db)) -> Machine:
    machine = db.scalar(
        select(Machine).where(Machine.id == machine_id).options(*_machine_options())
    )
    if machine is None:
        raise HTTPException(
            status_code=404, detail=f"Machine {machine_id} was not found"
        )
    return machine
