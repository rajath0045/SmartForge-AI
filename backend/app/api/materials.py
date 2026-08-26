from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models import Material
from app.schemas.inventory import MaterialRead

router = APIRouter(prefix="/materials", tags=["materials"])


def _material_options():
    return (selectinload(Material.inventory_records), selectinload(Material.arrivals))


@router.get("", response_model=list[MaterialRead])
def list_materials(
    shortage_only: bool = False, db: Session = Depends(get_db)
) -> list[Material]:
    materials = list(
        db.scalars(
            select(Material).options(*_material_options()).order_by(Material.code)
        )
        .unique()
        .all()
    )
    if shortage_only:
        return [
            material
            for material in materials
            if any(
                record.available_quantity <= record.safety_stock_quantity
                for record in material.inventory_records
            )
        ]
    return materials


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(material_id: str, db: Session = Depends(get_db)) -> Material:
    material = db.scalar(
        select(Material).where(Material.id == material_id).options(*_material_options())
    )
    if material is None:
        raise HTTPException(
            status_code=404, detail=f"Material {material_id} was not found"
        )
    return material
