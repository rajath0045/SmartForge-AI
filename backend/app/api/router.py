from fastapi import APIRouter

from . import (
    analytics,
    control,
    dashboard,
    decisions,
    machines,
    master_data,
    materials,
    orders,
    schedule,
    workforce,
)

api_router = APIRouter()
api_router.include_router(dashboard.router)
api_router.include_router(machines.router)
api_router.include_router(workforce.router)
api_router.include_router(orders.router)
api_router.include_router(materials.router)
api_router.include_router(schedule.router)
api_router.include_router(analytics.router)
api_router.include_router(control.router)
api_router.include_router(master_data.router)
api_router.include_router(decisions.router)
