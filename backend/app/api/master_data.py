from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CostConfiguration, Customer, PartFamily, Shift
from app.schemas.common import ORMModel
from app.schemas.order import CustomerRead, PartFamilyRead
from app.schemas.workforce import ShiftRead

router = APIRouter(tags=["master data"])


class CostConfigurationRead(ORMModel):
    key: str
    value: float
    unit: str
    category: str
    description: str


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(db: Session = Depends(get_db)) -> list[Customer]:
    return list(
        db.scalars(select(Customer).order_by(Customer.tier, Customer.name)).all()
    )


@router.get("/part-families", response_model=list[PartFamilyRead])
def list_part_families(db: Session = Depends(get_db)) -> list[PartFamily]:
    return list(db.scalars(select(PartFamily).order_by(PartFamily.code)).all())


@router.get("/shifts", response_model=list[ShiftRead])
def list_shifts(db: Session = Depends(get_db)) -> list[Shift]:
    return list(db.scalars(select(Shift).order_by(Shift.start_time)).all())


@router.get("/cost-config", response_model=list[CostConfigurationRead])
def get_cost_configuration(db: Session = Depends(get_db)) -> list[CostConfiguration]:
    return list(
        db.scalars(
            select(CostConfiguration).order_by(
                CostConfiguration.category, CostConfiguration.key
            )
        ).all()
    )
