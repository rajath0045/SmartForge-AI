from __future__ import annotations

from datetime import date, time

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import MachineType, OperationType, ResourceStatus

from .common import TimestampMixin


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    day_of_week: Mapped[int | None] = mapped_column(Integer)
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sunday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capacity_hours: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    labour_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    operators: Mapped[list[Operator]] = relationship(back_populates="shift")


class Operator(TimestampMixin, Base):
    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    shift_id: Mapped[str] = mapped_column(
        ForeignKey("shifts.id"), index=True, nullable=False
    )
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, native_enum=False), default=ResourceStatus.AVAILABLE
    )
    experience_years: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    overtime_eligible: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    max_overtime_hours_week: Mapped[float] = mapped_column(Float, default=8.0)
    hourly_rate: Mapped[float] = mapped_column(Float, default=220.0, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(24))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    shift: Mapped[Shift] = relationship(back_populates="operators", lazy="joined")
    skills: Mapped[list[OperatorSkill]] = relationship(
        back_populates="operator", cascade="all, delete-orphan", lazy="selectin"
    )
    availability: Mapped[list[OperatorAvailability]] = relationship(
        back_populates="operator", cascade="all, delete-orphan"
    )


class OperatorSkill(Base):
    __tablename__ = "operator_skills"
    __table_args__ = (
        UniqueConstraint(
            "operator_id", "operation_type", "machine_type", name="uq_operator_skill"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator_id: Mapped[str] = mapped_column(
        ForeignKey("operators.id", ondelete="CASCADE"), index=True, nullable=False
    )
    operation_type: Mapped[OperationType] = mapped_column(
        Enum(OperationType, native_enum=False), index=True, nullable=False
    )
    machine_type: Mapped[MachineType] = mapped_column(
        Enum(MachineType, native_enum=False), index=True, nullable=False
    )
    proficiency: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    certified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    certification_expires_on: Mapped[date | None] = mapped_column(Date)

    operator: Mapped[Operator] = relationship(back_populates="skills")


class OperatorAvailability(Base):
    __tablename__ = "operator_availability"
    __table_args__ = (
        UniqueConstraint(
            "operator_id", "work_date", "shift_id", name="uq_operator_day_shift"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator_id: Mapped[str] = mapped_column(
        ForeignKey("operators.id", ondelete="CASCADE"), index=True, nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    shift_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), nullable=False)
    status: Mapped[ResourceStatus] = mapped_column(
        Enum(ResourceStatus, native_enum=False), default=ResourceStatus.AVAILABLE
    )
    available_hours: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(160))

    operator: Mapped[Operator] = relationship(back_populates="availability")
    shift: Mapped[Shift] = relationship()
