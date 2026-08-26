from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    # Entering the context exercises the same initialization and deterministic,
    # idempotent seed path used by a real API process.
    with TestClient(app) as test_client:
        yield test_client


def test_live_schedule_generation_and_plan_comparison(client: TestClient):
    generated = client.post(
        "/api/schedule/generate",
        json={"mode": "MOST_ROBUST", "exact": False},
    )
    assert generated.status_code == 200
    schedule = generated.json()
    assert schedule["valid"] is True
    assert schedule["status"] == "FEASIBLE"
    assert schedule["solver"] == "HEURISTIC"
    assert len(schedule["operations"]) == 96
    assert schedule["violations"] == []

    response = client.get("/api/schedule/comparison")
    assert response.status_code == 200
    comparison = response.json()
    assert len(comparison["plans"]) == 3
    assert all(plan["isValid"] for plan in comparison["plans"])
    assert comparison["recommendedMode"] in {
        "CHEAPEST",
        "MOST_ON_TIME",
        "MOST_ROBUST",
    }


def test_rfq_returns_explainable_validated_decision(client: TestClient):
    response = client.post(
        "/api/rfq/evaluate",
        json={
            "customer": "Apex Driveline",
            "tier": "Tier 1",
            "part": "AX-206",
            "quantity": 1200,
            "requestedDate": "2026-09-04",
            "sellingPrice": 840000,
            "latePenalty": 76000,
            "operations": ["Turning", "Milling", "Grinding", "Inspection"],
            "materialAvailable": True,
        },
    )
    assert response.status_code == 200
    decision = response.json()
    assert decision["valid"] is True
    assert decision["violations"] == []
    assert decision["decision"]
    assert len(decision["capacityChecks"]) == 4
    assert decision["reasons"]


def test_disruption_and_simulation_return_valid_recovery_plans(client: TestClient):
    disruption = client.post(
        "/api/disruptions",
        json={
            "type": "MACHINE_BREAKDOWN",
            "resource": "GRIND-01",
            "start": "2026-09-02T11:00:00",
            "durationHours": 8,
            "notes": "Eight-hour grinding outage",
        },
    )
    assert disruption.status_code == 200
    recovery = disruption.json()
    assert recovery["valid"] is True
    assert recovery["violations"] == []
    assert recovery["jobsMoved"] > 0
    assert recovery["ownerCall"]["contact"]

    simulation = client.post(
        "/api/simulation/run",
        json={"scenario": "grinder-breakdown", "magnitude": 8},
    )
    assert simulation.status_code == 200
    scenario = simulation.json()
    assert scenario["valid"] is True
    assert scenario["violations"] == []
    assert scenario["label"] == "Grinder Breakdown"
    assert scenario["recommendation"]

    power = client.post(
        "/api/simulation/run",
        json={"scenario": "power-failure", "magnitude": 8},
    )
    assert power.status_code == 200
    power_scenario = power.json()
    assert power_scenario["valid"] is True
    assert power_scenario["violations"] == []
    assert power_scenario["delivery"] <= power_scenario["baseline"]["delivery"]

    investment = client.post(
        "/api/simulation/run",
        json={"scenario": "new-grinder", "magnitude": 1},
    )
    assert investment.status_code == 200
    investment_scenario = investment.json()
    assert investment_scenario["valid"] is True
    assert investment_scenario["bottleneckLoad"] < investment_scenario["baseline"][
        "bottleneckLoad"
    ]
