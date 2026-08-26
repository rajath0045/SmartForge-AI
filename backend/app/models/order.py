from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import (
    CustomerTier,
    MachineType,
    OperationType,
    OrderStatus,
    RiskLevel,
)

from .common import TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    tier: Mapped[CustomerTier] = mapped_column(
        Enum(CustomerTier, native_enum=False), index=True, nullable=False
    )
    strategic_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    default_penalty_per_day: Mapped[float] = mapped_column(Float, default=0.0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=45)
    contact_name: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(24))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    orders: Mapped[list[ProductionOrder]] = relationship(back_populates="customer")


class PartFamily(TimestampMixin, Base):
    __tablename__ = "part_families"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    code: Mapped[str] = mapped_column(
        String(24), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    fixture_code: Mapped[str] = mapped_column(String(32), nullable=False)
    default_material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id"), index=True, nullable=False
    )
    typical_reject_rate: Mapped[float] = mapped_column(Float, default=0.03)

    default_material: Mapped[object] = relationship("Material")
    orders: Mapped[list[ProductionOrder]] = relationship(back_populates="part_family")


class ProductionOrder(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id"), index=True, nullable=False
    )
    part_family_id: Mapped[str] = mapped_column(
        ForeignKey("part_families.id"), index=True, nullable=False
    )
    part_number: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    promised_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False), index=True, nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False), default=RiskLevel.LOW, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    unit_selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    unit_material_cost: Mapped[float] = mapped_column(Float, nullable=False)
    expected_production_cost: Mapped[float] = mapped_column(Float, default=0.0)
    late_penalty_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("materials.id"), index=True, nullable=False
    )
    material_required_qty: Mapped[float] = mapped_column(Float, nullable=False)
    material_available_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quality_reject_rate: Mapped[float] = mapped_column(Float, default=0.03)
    delivery_probability: Mapped[float] = mapped_column(Float, default=0.9)
    expected_completion_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="orders", lazy="joined")
    part_family: Mapped[PartFamily] = relationship(
        back_populates="orders", lazy="joined"
    )
    material: Mapped[object] = relationship("Material")
    operations: Mapped[list[OrderOperation]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderOperation.sequence",
        lazy="selectin",
        foreign_keys="OrderOperation.order_id",
    )

    @property
    def revenue(self) -> float:
        return round(self.quantity * self.unit_selling_price, 2)

    @property
    def material_cost(self) -> float:
        return round(self.quantity * self.unit_material_cost, 2)

    @property
    def expected_profit(self) -> float:
        return round(
            self.revenue - self.material_cost - self.expected_production_cost, 2
        )


class OrderOperation(TimestampMixin, Base):
    __tablename__ = "order_operations"
    __table_args__ = (
        UniqueConstraint("order_id", "sequence", name="uq_order_operation_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[OperationType] = mapped_column(
        Enum(OperationType, native_enum=False), index=True, nullable=False
    )
    required_machine_type: Mapped[MachineType] = mapped_column(
        Enum(MachineType, native_enum=False), index=True, nullable=False
    )
    required_skill: Mapped[OperationType] = mapped_column(
        Enum(OperationType, native_enum=False), nullable=False
    )
    setup_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    run_minutes_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    planned_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    predecessor_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_operations.id"), nullable=True
    )
    outsource_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    outsource_cost_per_unit: Mapped[float | None] = mapped_column(Float)

    order: Mapped[ProductionOrder] = relationship(
        back_populates="operations", foreign_keys=[order_id]
    )
    predecessor: Mapped[OrderOperation | None] = relationship(
        remote_side=[id], foreign_keys=[predecessor_id]
    )
    eligible_machines: Mapped[list[OperationMachineEligibility]] = relationship(
        back_populates="operation", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def processing_minutes(self) -> int:
        return round(
            self.setup_minutes + self.run_minutes_per_unit * self.planned_quantity
        )


class OperationMachineEligibility(Base):
    __tablename__ = "operation_machine_eligibility"
    __table_args__ = (
        UniqueConstraint(
            "order_operation_id", "machine_id", name="uq_operation_machine"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_operation_id: Mapped[int] = mapped_column(
        ForeignKey("order_operations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    preference_rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    operation: Mapped[OrderOperation] = relationship(back_populates="eligible_machines")
    machine: Mapped[object] = relationship("Machine")
