from __future__ import annotations

from datetime import datetime

from .common import APIModel


class DashboardKPI(APIModel):
    active_orders: int
    completed_orders: int
    orders_at_risk: int
    delayed_orders: int
    on_time_delivery_percent: float
    machine_utilization_percent: float
    oee_percent: float
    labour_utilization_percent: float
    bottleneck_utilization_percent: float
    production_cost: float
    revenue: float
    expected_profit: float
    overtime_cost: float
    late_penalties: float
    energy_cost: float
    generator_cost: float
    changeover_losses: float
    rework_cost: float


class FactoryStatus(APIModel):
    machines_running: int
    machines_idle: int
    machines_setup: int
    machines_maintenance: int
    machines_broken: int
    operators_present: int
    operators_absent: int
    grid_power_status: str
    generator_status: str
    material_shortages: int


class BottleneckSummary(APIModel):
    machine_id: str
    machine_name: str
    utilization_percent: float
    committed_hours: float
    available_hours: float
    dependent_orders: int
    status: str


class DashboardAlert(APIModel):
    id: str
    severity: str
    category: str
    title: str
    description: str
    affected_resource: str | None = None
    estimated_financial_impact: float = 0.0
    recommended_action: str


class DashboardRead(APIModel):
    as_of: datetime
    factory_name: str
    kpis: DashboardKPI
    factory_status: FactoryStatus
    bottleneck: BottleneckSummary
    action_required: list[DashboardAlert]
