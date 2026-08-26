from __future__ import annotations

from datetime import date

from .common import ORMModel


class InventoryRead(ORMModel):
    id: int
    location: str
    on_hand_quantity: float
    allocated_quantity: float
    available_quantity: float
    safety_stock_quantity: float
    reorder_point: float


class MaterialArrivalRead(ORMModel):
    id: int
    purchase_order: str
    quantity: float
    expected_date: date
    revised_date: date | None
    effective_date: date
    delay_probability: float
    supplier_name: str
    status: str


class MaterialRead(ORMModel):
    id: str
    code: str
    name: str
    grade: str
    unit: str
    unit_cost: float
    supplier_name: str
    standard_lead_days: int
    delay_risk: float
    on_hand_quantity: float
    allocated_quantity: float
    available_quantity: float
    inventory_records: list[InventoryRead]
    arrivals: list[MaterialArrivalRead]
