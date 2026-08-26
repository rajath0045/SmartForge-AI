from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import (
    DisruptionStatus,
    DisruptionType,
    PowerEventType,
    RiskLevel,
)

from .common import TimestampMixin


class PowerEvent(TimestampMixin, Base):
    __tablename__ = "power_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[PowerEventType] = mapped_column(
        Enum(PowerEventType, native_enum=False), nullable=False
    )
    grid_available: Mapped[bool] = mapped_column(Boolean, default=True)
    generator_available: Mapped[bool] = mapped_column(Boolean, default=True)
    generator_capacity_kw: Mapped[float] = mapped_column(Float, default=180.0)
    grid_cost_per_kwh: Mapped[float] = mapped_column(Float, default=8.4)
    generator_cost_per_kwh: Mapped[float] = mapped_column(Float, default=28.5)
    probability: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[str | None] = mapped_column(Text)


class Disruption(TimestampMixin, Base):
    __tablename__ = "disruptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disruption_type: Mapped[DisruptionType] = mapped_column(
        Enum(DisruptionType, native_enum=False), index=True, nullable=False
    )
    severity: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False), index=True, nullable=False
    )
    status: Mapped[DisruptionStatus] = mapped_column(
        Enum(DisruptionStatus, native_enum=False), default=DisruptionStatus.OPEN
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materials.id"))
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    estimated_financial_impact: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_impact_hours: Mapped[float] = mapped_column(Float, default=0.0)

    machine: Mapped[object | None] = relationship("Machine")
    operator: Mapped[object | None] = relationship("Operator")
    order: Mapped[object | None] = relationship("ProductionOrder")
    material: Mapped[object | None] = relationship("Material")


class QualityEvent(TimestampMixin, Base):
    __tablename__ = "quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), index=True, nullable=False
    )
    order_operation_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_operations.id")
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    inspected_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rework_quantity: Mapped[int] = mapped_column(Integer, default=0)
    scrap_quantity: Mapped[int] = mapped_column(Integer, default=0)
    defect_code: Mapped[str] = mapped_column(String(50), nullable=False)
    root_cause: Mapped[str | None] = mapped_column(String(180))
    rework_cost: Mapped[float] = mapped_column(Float, default=0.0)
    schedule_impact_hours: Mapped[float] = mapped_column(Float, default=0.0)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped[object] = relationship("ProductionOrder")
    order_operation: Mapped[object | None] = relationship("OrderOperation")
