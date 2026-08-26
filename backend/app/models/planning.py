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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import OperationStatus, ScheduleMode, ScheduleStatus

from .common import TimestampMixin, utc_now


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[ScheduleMode] = mapped_column(
        Enum(ScheduleMode, native_enum=False), index=True, nullable=False
    )
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, native_enum=False),
        default=ScheduleStatus.DRAFT,
        index=True,
    )
    horizon_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    solver_status: Mapped[str] = mapped_column(String(40), default="SEEDED")
    objective_value: Mapped[float | None] = mapped_column(Float)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    baseline_schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    operations: Mapped[list[ScheduleOperation]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleOperation.start_at",
        lazy="selectin",
    )
    baseline_schedule: Mapped[Schedule | None] = relationship(remote_side=[id])


class ScheduleOperation(TimestampMixin, Base):
    __tablename__ = "schedule_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_operation_id: Mapped[int] = mapped_column(
        ForeignKey("order_operations.id"), index=True, nullable=False
    )
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id"), index=True, nullable=False
    )
    operator_id: Mapped[str] = mapped_column(
        ForeignKey("operators.id"), index=True, nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OperationStatus] = mapped_column(
        Enum(OperationStatus, native_enum=False), default=OperationStatus.PLANNED
    )
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), nullable=False)
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_generator: Mapped[bool] = mapped_column(Boolean, default=False)
    is_changeover: Mapped[bool] = mapped_column(Boolean, default=False)
    changeover_minutes: Mapped[int] = mapped_column(Integer, default=0)
    operation_cost: Mapped[float] = mapped_column(Float, default=0.0)
    energy_cost: Mapped[float] = mapped_column(Float, default=0.0)
    labour_cost: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text)

    schedule: Mapped[Schedule] = relationship(back_populates="operations")
    order_operation: Mapped[object] = relationship("OrderOperation", lazy="joined")
    machine: Mapped[object] = relationship("Machine", lazy="joined")
    operator: Mapped[object] = relationship("Operator", lazy="joined")
    shift: Mapped[object] = relationship("Shift", lazy="joined")

    @property
    def duration_minutes(self) -> int:
        return max(0, round((self.end_at - self.start_at).total_seconds() / 60))


class ChangeoverMatrix(Base):
    __tablename__ = "changeover_matrix"
    __table_args__ = (
        UniqueConstraint(
            "from_part_family_id",
            "to_part_family_id",
            "machine_type",
            name="uq_changeover_transition",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_part_family_id: Mapped[str] = mapped_column(
        ForeignKey("part_families.id"), nullable=False
    )
    to_part_family_id: Mapped[str] = mapped_column(
        ForeignKey("part_families.id"), nullable=False
    )
    machine_type: Mapped[str] = mapped_column(String(32), nullable=False)
    changeover_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    changeover_cost: Mapped[float] = mapped_column(Float, nullable=False)
    same_fixture: Mapped[bool] = mapped_column(Boolean, default=False)

    from_part_family: Mapped[object] = relationship(
        "PartFamily", foreign_keys=[from_part_family_id]
    )
    to_part_family: Mapped[object] = relationship(
        "PartFamily", foreign_keys=[to_part_family_id]
    )
