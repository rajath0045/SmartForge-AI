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
    MachineStatus,
    MachineType,
    OperationType,
    WindowStatus,
)

from .common import TimestampMixin


class Machine(TimestampMixin, Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    machine_type: Mapped[MachineType] = mapped_column(
        Enum(MachineType, native_enum=False), index=True, nullable=False
    )
    status: Mapped[MachineStatus] = mapped_column(
        Enum(MachineStatus, native_enum=False), index=True, nullable=False
    )
    manufacturer: Mapped[str | None] = mapped_column(String(80))
    model_number: Mapped[str | None] = mapped_column(String(80))
    commissioned_year: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(80), default="Main shop")
    power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    hourly_cost: Mapped[float] = mapped_column(Float, nullable=False)
    total_running_hours: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    health_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    availability_rate: Mapped[float] = mapped_column(
        Float, default=0.95, nullable=False
    )
    performance_rate: Mapped[float] = mapped_column(Float, default=0.90, nullable=False)
    quality_rate: Mapped[float] = mapped_column(Float, default=0.97, nullable=False)
    mtbf_hours: Mapped[float] = mapped_column(Float, default=500.0, nullable=False)
    mttr_hours: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    capabilities: Mapped[list[MachineCapability]] = relationship(
        back_populates="machine", cascade="all, delete-orphan", lazy="selectin"
    )
    breakdowns: Mapped[list[MachineBreakdown]] = relationship(
        back_populates="machine", cascade="all, delete-orphan"
    )
    maintenance_windows: Mapped[list[MaintenanceWindow]] = relationship(
        back_populates="machine", cascade="all, delete-orphan"
    )

    @property
    def oee(self) -> float:
        return round(
            self.availability_rate * self.performance_rate * self.quality_rate * 100,
            1,
        )


class MachineCapability(Base):
    __tablename__ = "machine_capabilities"
    __table_args__ = (
        UniqueConstraint("machine_id", "operation_type", name="uq_machine_capability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    operation_type: Mapped[OperationType] = mapped_column(
        Enum(OperationType, native_enum=False), index=True, nullable=False
    )
    setup_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    efficiency: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    min_batch_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_batch_size: Mapped[int | None] = mapped_column(Integer)

    machine: Mapped[Machine] = relationship(back_populates="capabilities")


class MachineBreakdown(Base):
    __tablename__ = "machine_breakdowns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(40))
    lost_production_hours: Mapped[float] = mapped_column(Float, default=0.0)
    financial_impact: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[WindowStatus] = mapped_column(
        Enum(WindowStatus, native_enum=False), default=WindowStatus.COMPLETED
    )

    machine: Mapped[Machine] = relationship(back_populates="breakdowns")


class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    maintenance_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[WindowStatus] = mapped_column(
        Enum(WindowStatus, native_enum=False), default=WindowStatus.PLANNED
    )
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    technician: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)

    machine: Mapped[Machine] = relationship(back_populates="maintenance_windows")
