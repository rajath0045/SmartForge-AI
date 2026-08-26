from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

from .common import TimestampMixin


class Material(TimestampMixin, Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    grade: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="kg", nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(120), nullable=False)
    standard_lead_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    delay_risk: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)

    inventory_records: Mapped[list[Inventory]] = relationship(
        back_populates="material", cascade="all, delete-orphan", lazy="selectin"
    )
    arrivals: Mapped[list[MaterialArrival]] = relationship(
        back_populates="material", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def on_hand_quantity(self) -> float:
        return sum(record.on_hand_quantity for record in self.inventory_records)

    @property
    def allocated_quantity(self) -> float:
        return sum(record.allocated_quantity for record in self.inventory_records)

    @property
    def available_quantity(self) -> float:
        return max(0.0, self.on_hand_quantity - self.allocated_quantity)


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("material_id", "location", name="uq_material_location"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    location: Mapped[str] = mapped_column(String(80), default="Raw Material Bay")
    on_hand_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    allocated_quantity: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    safety_stock_quantity: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    reorder_point: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    material: Mapped[Material] = relationship(back_populates="inventory_records")

    @property
    def available_quantity(self) -> float:
        return max(0.0, self.on_hand_quantity - self.allocated_quantity)


class MaterialArrival(TimestampMixin, Base):
    __tablename__ = "material_arrivals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purchase_order: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    expected_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    revised_date: Mapped[date | None] = mapped_column(Date)
    delay_probability: Mapped[float] = mapped_column(
        Float, default=0.05, nullable=False
    )
    supplier_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="EXPECTED", nullable=False)

    material: Mapped[Material] = relationship(back_populates="arrivals")

    @property
    def effective_date(self) -> date:
        return self.revised_date or self.expected_date
