from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import DisruptionStatus, RecommendationStatus
from app.models import Disruption, PowerEvent, Recommendation

router = APIRouter(tags=["control tower"])


@router.get("/risks")
def list_risks(db: Session = Depends(get_db)) -> list[dict]:
    disruptions = list(
        db.scalars(
            select(Disruption)
            .where(Disruption.status != DisruptionStatus.RESOLVED)
            .order_by(Disruption.start_at)
        ).all()
    )
    return [
        {
            "id": item.id,
            "severity": item.severity.value,
            "category": item.disruption_type.value,
            "status": item.status.value,
            "title": item.title,
            "description": item.description,
            "startAt": item.start_at,
            "endAt": item.end_at,
            "machineId": item.machine_id,
            "operatorId": item.operator_id,
            "orderId": item.order_id,
            "materialId": item.material_id,
            "probability": item.details.get("probability", 1.0),
            "estimatedFinancialImpact": item.estimated_financial_impact,
            "deliveryImpactHours": item.delivery_impact_hours,
        }
        for item in disruptions
    ]


@router.get("/recommendations")
def list_recommendations(
    pending_only: bool = True, db: Session = Depends(get_db)
) -> list[dict]:
    statement = select(Recommendation).order_by(Recommendation.created_at.desc())
    if pending_only:
        statement = statement.where(
            Recommendation.status == RecommendationStatus.PENDING
        )
    recommendations = list(db.scalars(statement).all())
    return [
        {
            "id": item.id,
            "category": item.category,
            "severity": item.severity.value,
            "title": item.title,
            "recommendedAction": item.recommended_action,
            "explanation": item.explanation,
            "financialBenefit": item.financial_benefit,
            "estimatedCost": item.estimated_cost,
            "netBenefit": item.financial_benefit - item.estimated_cost,
            "confidence": item.confidence,
            "status": item.status.value,
            "machineId": item.machine_id,
            "orderId": item.order_id,
            "requiresApproval": item.requires_approval,
        }
        for item in recommendations
    ]


@router.get("/power")
def get_power_events(db: Session = Depends(get_db)) -> list[dict]:
    events = list(db.scalars(select(PowerEvent).order_by(PowerEvent.start_at)).all())
    return [
        {
            "id": item.id,
            "startAt": item.start_at,
            "endAt": item.end_at,
            "eventType": item.event_type.value,
            "gridAvailable": item.grid_available,
            "generatorAvailable": item.generator_available,
            "generatorCapacityKw": item.generator_capacity_kw,
            "gridCostPerKwh": item.grid_cost_per_kwh,
            "generatorCostPerKwh": item.generator_cost_per_kwh,
            "probability": item.probability,
            "notes": item.notes,
        }
        for item in events
    ]
