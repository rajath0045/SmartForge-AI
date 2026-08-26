from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.enums import MachineType, ResourceStatus
from app.models import Operator, OperatorSkill
from app.schemas.workforce import OperatorRead

router = APIRouter(prefix="/operators", tags=["workforce"])


@router.get("", response_model=list[OperatorRead])
def list_operators(
    shift_id: str | None = None,
    status: ResourceStatus | None = None,
    machine_type: MachineType | None = None,
    db: Session = Depends(get_db),
) -> list[Operator]:
    statement = (
        select(Operator)
        .options(selectinload(Operator.skills), selectinload(Operator.shift))
        .order_by(Operator.id)
    )
    if shift_id is not None:
        statement = statement.where(Operator.shift_id == shift_id)
    if status is not None:
        statement = statement.where(Operator.status == status)
    if machine_type is not None:
        statement = statement.join(Operator.skills).where(
            OperatorSkill.machine_type == machine_type,
            OperatorSkill.certified.is_(True),
        )
    return list(db.scalars(statement).unique().all())
