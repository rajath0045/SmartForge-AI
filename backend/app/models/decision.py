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
    CustomerTier,
    MachineType,
    OperationType,
    RecommendationStatus,
    RFQStatus,
    RiskLevel,
)

from .common import TimestampMixin


class RFQ(TimestampMixin, Base):
    __tablename__ = "rfqs"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    customer_name: Mapped[str] = mapped_column(String(140), nullable=False)
    customer_tier: Mapped[CustomerTier] = mapped_column(
        Enum(CustomerTier, native_enum=False), nullable=False
    )
    part_number: Mapped[str] = mapped_column(String(50), nullable=False)
    part_family_id: Mapped[str] = mapped_column(ForeignKey("part_families.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_delivery_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    unit_selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    late_penalty_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"), nullable=False)
    material_required_qty: Mapped[float] = mapped_column(Float, nullable=False)
    material_available_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[RFQStatus] = mapped_column(
        Enum(RFQStatus, native_enum=False), default=RFQStatus.PENDING
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    attractiveness_score: Mapped[float | None] = mapped_column(Float)
    recommended_promise_date: Mapped[datetime | None] = mapped_column(DateTime)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[object | None] = relationship("Customer")
    part_family: Mapped[object] = relationship("PartFamily")
    material: Mapped[object] = relationship("Material")
    operations: Mapped[list[RFQOperation]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def revenue(self) -> float:
        return round(self.quantity * self.unit_selling_price, 2)


class RFQOperation(Base):
    __tablename__ = "rfq_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rfq_id: Mapped[str] = mapped_column(
        ForeignKey("rfqs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[OperationType] = mapped_column(
        Enum(OperationType, native_enum=False), nullable=False
    )
    required_machine_type: Mapped[MachineType] = mapped_column(
        Enum(MachineType, native_enum=False), nullable=False
    )
    setup_minutes: Mapped[int] = mapped_column(Integer, default=30)
    run_minutes_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    outsource_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

    rfq: Mapped[RFQ] = relationship(back_populates="operations")


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    severity: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    financial_benefit: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, native_enum=False),
        default=RecommendationStatus.PENDING,
    )
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    disruption_id: Mapped[int | None] = mapped_column(ForeignKey("disruptions.id"))
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    machine: Mapped[object | None] = relationship("Machine")
    order: Mapped[object | None] = relationship("ProductionOrder")
    disruption: Mapped[object | None] = relationship("Disruption")


class CostConfiguration(TimestampMixin, Base):
    __tablename__ = "cost_configurations"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
