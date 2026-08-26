from __future__ import annotations

import argparse
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine, init_db
from app.core.enums import (
    CustomerTier,
    DisruptionStatus,
    DisruptionType,
    MachineStatus,
    MachineType,
    OperationStatus,
    OperationType,
    OrderStatus,
    PowerEventType,
    RecommendationStatus,
    ResourceStatus,
    RFQStatus,
    RiskLevel,
    ScheduleMode,
    ScheduleStatus,
    WindowStatus,
)
from app.models import (
    RFQ,
    ChangeoverMatrix,
    CostConfiguration,
    Customer,
    Disruption,
    Inventory,
    Machine,
    MachineBreakdown,
    MachineCapability,
    MaintenanceWindow,
    Material,
    MaterialArrival,
    OperationMachineEligibility,
    Operator,
    OperatorAvailability,
    OperatorSkill,
    OrderOperation,
    PartFamily,
    PowerEvent,
    ProductionOrder,
    QualityEvent,
    Recommendation,
    RFQOperation,
    Schedule,
    ScheduleOperation,
    Shift,
)

SEED = 20260901
DEMO_NOW = datetime(2026, 9, 1, 10, 30)
HORIZON_START = datetime(2026, 9, 1, 6, 0)
HORIZON_END = HORIZON_START + timedelta(days=14)


MACHINE_SPECS = [
    ("CNC-L01", "CNC Lathe 01", MachineType.CNC_LATHE, 18.5, 1_240.0),
    ("CNC-L02", "CNC Lathe 02", MachineType.CNC_LATHE, 20.0, 1_280.0),
    ("CNC-L03", "CNC Lathe 03", MachineType.CNC_LATHE, 18.5, 1_220.0),
    ("CNC-L04", "CNC Lathe 04", MachineType.CNC_LATHE, 22.0, 1_350.0),
    ("CNC-L05", "CNC Lathe 05", MachineType.CNC_LATHE, 16.0, 1_160.0),
    ("MILL-01", "VMC Milling 01", MachineType.MILLING, 24.0, 1_520.0),
    ("MILL-02", "VMC Milling 02", MachineType.MILLING, 26.0, 1_580.0),
    ("MILL-03", "VMC Milling 03", MachineType.MILLING, 21.0, 1_460.0),
    ("DRILL-01", "Radial Drill 01", MachineType.DRILLING, 7.5, 720.0),
    ("DRILL-02", "CNC Drill 02", MachineType.DRILLING, 9.0, 790.0),
    ("DRILL-03", "CNC Drill 03", MachineType.DRILLING, 8.0, 750.0),
    ("GRIND-01", "Critical Grinder 01", MachineType.GRINDING, 28.0, 1_860.0),
    ("INSPECT-01", "CMM Inspection 01", MachineType.INSPECTION, 4.5, 680.0),
    ("INSPECT-02", "Inspection Cell 02", MachineType.INSPECTION, 3.0, 520.0),
]

OPERATOR_NAMES = [
    "Arun Kumar",
    "Manoj R",
    "Senthil Kumar",
    "Prakash B",
    "Vignesh S",
    "Ravi Chandran",
    "Naveen K",
    "Suresh M",
    "Dinesh Raj",
    "Karthik P",
    "Balaji N",
    "Mohan S",
    "Girish B",
    "Vinod Kumar",
    "Saravanan R",
    "Ramesh K",
    "Deepak M",
    "Ashok S",
    "Sathish P",
    "Murugan V",
    "Anand Raj",
    "Kiran Kumar",
    "Madesh B",
    "Lokesh N",
    "Praveen S",
    "Harish K",
    "Shankar M",
    "Raghavan P",
    "Elango S",
    "Ganesh R",
    "Ajith Kumar",
    "Vijay B",
    "Gowtham N",
    "Chandru S",
    "Sanjay K",
    "Hemalatha R",
    "Kavitha M",
    "Meena S",
    "Divya P",
    "Lakshmi N",
]


def _machine_operation(machine_type: MachineType) -> OperationType:
    return {
        MachineType.CNC_LATHE: OperationType.TURNING,
        MachineType.MILLING: OperationType.MILLING,
        MachineType.DRILLING: OperationType.DRILLING,
        MachineType.GRINDING: OperationType.GRINDING,
        MachineType.INSPECTION: OperationType.INSPECTION,
    }[machine_type]


def _seed_machines(db: Session, rng: random.Random) -> list[Machine]:
    statuses = {
        "CNC-L01": MachineStatus.RUNNING,
        "CNC-L02": MachineStatus.RUNNING,
        "CNC-L03": MachineStatus.BREAKDOWN,
        "CNC-L04": MachineStatus.IDLE,
        "CNC-L05": MachineStatus.RUNNING,
        "MILL-01": MachineStatus.RUNNING,
        "MILL-02": MachineStatus.SETUP,
        "MILL-03": MachineStatus.MAINTENANCE,
        "DRILL-01": MachineStatus.RUNNING,
        "DRILL-02": MachineStatus.IDLE,
        "DRILL-03": MachineStatus.RUNNING,
        "GRIND-01": MachineStatus.RUNNING,
        "INSPECT-01": MachineStatus.IDLE,
        "INSPECT-02": MachineStatus.IDLE,
    }
    machines: list[Machine] = []
    for index, (machine_id, name, machine_type, power_kw, hourly_cost) in enumerate(
        MACHINE_SPECS
    ):
        is_grinder = machine_type == MachineType.GRINDING
        health = 72.0 if is_grinder else round(79 + rng.random() * 18, 1)
        if machine_id == "CNC-L04":
            health = 64.0
        failure_count = 5 if machine_id == "CNC-L04" else rng.randint(1, 4)
        machine = Machine(
            id=machine_id,
            name=name,
            machine_type=machine_type,
            status=statuses[machine_id],
            manufacturer=(
                "Jyoti CNC" if "CNC" in machine_id else "Bharat Fritz Werner"
            ),
            model_number=f"SPW-{machine_type.value[:3]}-{index + 1:02d}",
            commissioned_year=2013 + index % 10,
            location="Bay A" if index < 8 else "Bay B",
            power_kw=power_kw,
            hourly_cost=hourly_cost,
            total_running_hours=round(5_600 + index * 780 + rng.random() * 900, 1),
            health_score=health,
            availability_rate=round(0.88 + rng.random() * 0.09, 3),
            performance_rate=round(0.84 + rng.random() * 0.11, 3),
            quality_rate=round(0.955 + rng.random() * 0.035, 3),
            mtbf_hours=round(310 + rng.random() * 510, 1),
            mttr_hours=round(2.1 + rng.random() * 4.8, 1),
            failure_count=failure_count,
            last_maintenance_at=DEMO_NOW - timedelta(days=12 + index * 2),
            notes="Single critical resource; protect with capacity buffer."
            if is_grinder
            else None,
        )
        operation = _machine_operation(machine_type)
        machine.capabilities.append(
            MachineCapability(
                operation_type=operation,
                setup_minutes=20 if machine_type == MachineType.INSPECTION else 35,
                efficiency=round(0.87 + rng.random() * 0.12, 2),
                min_batch_size=20,
                max_batch_size=5_000,
            )
        )
        if machine_id in {"CNC-L04", "MILL-02"}:
            machine.capabilities.append(
                MachineCapability(
                    operation_type=OperationType.REWORK,
                    setup_minutes=45,
                    efficiency=0.82,
                    min_batch_size=1,
                    max_batch_size=500,
                )
            )
        for failure_index in range(3):
            start = DEMO_NOW - timedelta(days=42 + index * 3 + failure_index * 67)
            duration = round(1.5 + rng.random() * 6.0, 1)
            machine.breakdowns.append(
                MachineBreakdown(
                    start_at=start,
                    end_at=start + timedelta(hours=duration),
                    reason=(
                        "Spindle vibration above limit"
                        if failure_index == 0
                        else "Hydraulic pressure fault"
                        if failure_index == 1
                        else "Tool changer sensor failure"
                    ),
                    failure_code=f"F-{index + 1:02d}{failure_index + 1}",
                    lost_production_hours=duration,
                    financial_impact=round(duration * hourly_cost * 1.7, 2),
                    status=WindowStatus.COMPLETED,
                )
            )
        maintenance_start = HORIZON_START + timedelta(days=4 + index % 7, hours=10)
        machine.maintenance_windows.append(
            MaintenanceWindow(
                start_at=maintenance_start,
                end_at=maintenance_start + timedelta(hours=2 + (index % 3)),
                maintenance_type="Preventive inspection",
                status=WindowStatus.PLANNED,
                estimated_cost=6_500 + index * 450,
                technician="SPW maintenance team",
                notes="Lubrication, alignment and safety interlock checks.",
                is_mandatory=True,
            )
        )
        machines.append(machine)
    # The current CNC-L03 fault is represented both in status and history.
    cnc3 = next(machine for machine in machines if machine.id == "CNC-L03")
    cnc3.breakdowns.append(
        MachineBreakdown(
            start_at=DEMO_NOW - timedelta(hours=1, minutes=15),
            end_at=DEMO_NOW + timedelta(hours=6, minutes=45),
            reason="Servo drive trip; contractor en route",
            failure_code="SERVO-07",
            lost_production_hours=8.0,
            financial_impact=78_000.0,
            status=WindowStatus.ACTIVE,
        )
    )
    db.add_all(machines)
    return machines


def _seed_workforce(db: Session, rng: random.Random) -> list[Operator]:
    shifts = [
        Shift(
            id="SHIFT-1",
            name="Shift 1",
            start_time=time(6, 0),
            end_time=time(14, 0),
            capacity_hours=8.0,
            labour_multiplier=1.0,
        ),
        Shift(
            id="SHIFT-2",
            name="Shift 2",
            start_time=time(14, 0),
            end_time=time(22, 0),
            capacity_hours=8.0,
            labour_multiplier=1.0,
        ),
        Shift(
            id="SHIFT-OT",
            name="Approved Overtime",
            start_time=time(22, 0),
            end_time=time(2, 0),
            capacity_hours=4.0,
            is_overtime=True,
            labour_multiplier=1.5,
        ),
        Shift(
            id="SHIFT-SUN",
            name="Sunday Recovery Shift",
            start_time=time(6, 0),
            end_time=time(14, 0),
            capacity_hours=8.0,
            is_overtime=True,
            is_sunday=True,
            labour_multiplier=2.0,
        ),
    ]
    db.add_all(shifts)

    skill_bands = [
        (range(1, 15), OperationType.TURNING, MachineType.CNC_LATHE),
        (range(15, 23), OperationType.MILLING, MachineType.MILLING),
        (range(23, 27), OperationType.DRILLING, MachineType.DRILLING),
        (range(27, 30), OperationType.GRINDING, MachineType.GRINDING),
        (range(30, 41), OperationType.INSPECTION, MachineType.INSPECTION),
    ]
    operators: list[Operator] = []
    for operator_number, name in enumerate(OPERATOR_NAMES, start=1):
        operation_type = OperationType.INSPECTION
        machine_type = MachineType.INSPECTION
        for number_range, skill_operation, skill_machine in skill_bands:
            if operator_number in number_range:
                operation_type = skill_operation
                machine_type = skill_machine
                break
        shift_id = "SHIFT-1" if operator_number % 2 else "SHIFT-2"
        status = (
            ResourceStatus.ABSENT
            if operator_number in {16, 28}
            else ResourceStatus.AVAILABLE
        )
        operator = Operator(
            id=f"OP-{operator_number:02d}",
            employee_code=f"SPW{operator_number:03d}",
            name=name,
            shift_id=shift_id,
            status=status,
            experience_years=round(1.5 + (operator_number % 12) * 0.7, 1),
            overtime_eligible=operator_number not in {7, 19, 36},
            max_overtime_hours_week=8.0 if operator_number % 4 else 6.0,
            hourly_rate=210.0 + (operator_number % 8) * 18.0,
            phone=f"+91 90000 {operator_number:05d}",
        )
        operator.skills.append(
            OperatorSkill(
                operation_type=operation_type,
                machine_type=machine_type,
                proficiency=2 + operator_number % 4,
                certified=True,
                certification_expires_on=date(2027, 12, 31),
            )
        )
        # Cross-skills create flexibility without adding grinder-qualified staff.
        if operator_number in {3, 8, 12}:
            operator.skills.append(
                OperatorSkill(
                    operation_type=OperationType.DRILLING,
                    machine_type=MachineType.DRILLING,
                    proficiency=3,
                    certified=True,
                )
            )
        if operator_number in {17, 20}:
            operator.skills.append(
                OperatorSkill(
                    operation_type=OperationType.TURNING,
                    machine_type=MachineType.CNC_LATHE,
                    proficiency=2,
                    certified=True,
                )
            )
        if operator_number in {31, 34}:
            operator.skills.append(
                OperatorSkill(
                    operation_type=OperationType.DRILLING,
                    machine_type=MachineType.DRILLING,
                    proficiency=3,
                    certified=True,
                )
            )
        if status == ResourceStatus.ABSENT:
            operator.availability.append(
                OperatorAvailability(
                    work_date=DEMO_NOW.date(),
                    shift_id=shift_id,
                    status=ResourceStatus.ABSENT,
                    available_hours=0.0,
                    reason="Unplanned sick leave",
                )
            )
        operators.append(operator)
    db.add_all(operators)
    return operators


def _seed_materials(db: Session) -> tuple[list[Material], list[PartFamily]]:
    material_specs = [
        (
            "MAT-EN8",
            "EN8-BAR",
            "EN8 Steel Bar",
            "EN8",
            82.0,
            "Salem Steel Traders",
            8_400,
            7_650,
        ),
        (
            "MAT-EN19",
            "EN19-BAR",
            "EN19 Alloy Bar",
            "EN19",
            118.0,
            "JSW Steel Service",
            6_100,
            5_900,
        ),
        (
            "MAT-20MN",
            "20MNCR5",
            "Case Hardening Steel",
            "20MnCr5",
            132.0,
            "Tata Steel Distribution",
            4_600,
            4_550,
        ),
        (
            "MAT-SS304",
            "SS304",
            "Stainless Steel 304",
            "SS304",
            248.0,
            "Ambica Steels",
            3_800,
            2_900,
        ),
        (
            "MAT-SGI",
            "SG-IRON",
            "Spheroidal Graphite Iron",
            "SG500/7",
            69.0,
            "Hosur Castings",
            9_500,
            7_300,
        ),
        (
            "MAT-AL",
            "AL6061",
            "Aluminium Billet",
            "AL6061-T6",
            226.0,
            "Jindal Aluminium",
            2_800,
            2_050,
        ),
    ]
    materials: list[Material] = []
    for index, (
        material_id,
        code,
        name,
        grade,
        unit_cost,
        supplier,
        on_hand,
        allocated,
    ) in enumerate(material_specs):
        material = Material(
            id=material_id,
            code=code,
            name=name,
            grade=grade,
            unit="kg",
            unit_cost=unit_cost,
            supplier_name=supplier,
            standard_lead_days=5 + index,
            delay_risk=0.06 + index * 0.025,
        )
        material.inventory_records.append(
            Inventory(
                location="Raw Material Bay",
                on_hand_quantity=float(on_hand),
                allocated_quantity=float(allocated),
                safety_stock_quantity=600.0 + index * 100,
                reorder_point=1_200.0 + index * 180,
            )
        )
        if index in {1, 2, 4}:
            expected = DEMO_NOW.date() + timedelta(days=2 + index)
            material.arrivals.append(
                MaterialArrival(
                    purchase_order=f"PO-2609-{index + 1:03d}",
                    quantity=2_200.0 + index * 450,
                    expected_date=expected,
                    revised_date=expected + timedelta(days=2) if index == 2 else None,
                    delay_probability=0.32 if index == 2 else 0.10,
                    supplier_name=supplier,
                    status="DELAYED" if index == 2 else "EXPECTED",
                )
            )
        materials.append(material)
    db.add_all(materials)

    family_specs = [
        ("PF-01", "AXLE", "Axle & Shaft", "FX-AX", "MAT-EN19", 0.024),
        ("PF-02", "HUB", "Wheel Hub", "FX-HB", "MAT-SGI", 0.031),
        ("PF-03", "GEAR", "Transmission Gear", "FX-GR", "MAT-20MN", 0.043),
        ("PF-04", "VALVE", "Precision Valve", "FX-VL", "MAT-SS304", 0.049),
        ("PF-05", "BRKT", "Mounting Bracket", "FX-BR", "MAT-EN8", 0.026),
        ("PF-06", "HOUSING", "Lightweight Housing", "FX-HS", "MAT-AL", 0.034),
    ]
    families = [
        PartFamily(
            id=family_id,
            code=code,
            name=name,
            fixture_code=fixture,
            default_material_id=material_id,
            typical_reject_rate=reject_rate,
        )
        for family_id, code, name, fixture, material_id, reject_rate in family_specs
    ]
    db.add_all(families)
    return materials, families


def _seed_customers(db: Session) -> list[Customer]:
    customer_specs = [
        (
            "CUST-01",
            "T1-01",
            "Apex Automotive Systems",
            CustomerTier.TIER_1,
            1.45,
            76_000,
        ),
        (
            "CUST-02",
            "T1-02",
            "Vector Mobility India",
            CustomerTier.TIER_1,
            1.38,
            68_000,
        ),
        ("CUST-03", "T1-03", "Kaveri Driveline", CustomerTier.TIER_1, 1.32, 61_000),
        (
            "CUST-04",
            "T2-01",
            "Orion Auto Components",
            CustomerTier.TIER_2,
            1.10,
            24_000,
        ),
        ("CUST-05", "T2-02", "Hosur Motion Works", CustomerTier.TIER_2, 1.05, 19_000),
        ("CUST-06", "T2-03", "Deccan Brake Systems", CustomerTier.TIER_2, 1.00, 15_000),
        ("CUST-07", "T3-01", "Nova Engineering", CustomerTier.TIER_3, 0.92, 8_500),
        ("CUST-08", "T3-02", "BluePeak Fabrication", CustomerTier.TIER_3, 0.88, 6_000),
    ]
    customers = [
        Customer(
            id=customer_id,
            code=code,
            name=name,
            tier=tier,
            strategic_weight=weight,
            default_penalty_per_day=penalty,
            payment_terms_days=30 if tier == CustomerTier.TIER_1 else 45,
            contact_name=f"Purchase Manager — {name.split()[0]}",
            contact_phone=f"+91 8041 55{index:04d}",
        )
        for index, (customer_id, code, name, tier, weight, penalty) in enumerate(
            customer_specs, start=1
        )
    ]
    db.add_all(customers)
    return customers


ROUTES: dict[str, list[tuple[OperationType, MachineType, float]]] = {
    "PF-01": [
        (OperationType.TURNING, MachineType.CNC_LATHE, 0.600),
        (OperationType.MILLING, MachineType.MILLING, 0.450),
        (OperationType.GRINDING, MachineType.GRINDING, 0.270),
        (OperationType.INSPECTION, MachineType.INSPECTION, 0.200),
    ],
    "PF-02": [
        (OperationType.TURNING, MachineType.CNC_LATHE, 0.550),
        (OperationType.DRILLING, MachineType.DRILLING, 0.350),
        (OperationType.GRINDING, MachineType.GRINDING, 0.216),
        (OperationType.INSPECTION, MachineType.INSPECTION, 0.180),
    ],
    "PF-03": [
        (OperationType.TURNING, MachineType.CNC_LATHE, 0.700),
        (OperationType.MILLING, MachineType.MILLING, 0.600),
        (OperationType.GRINDING, MachineType.GRINDING, 0.351),
        (OperationType.INSPECTION, MachineType.INSPECTION, 0.250),
    ],
    "PF-04": [
        (OperationType.TURNING, MachineType.CNC_LATHE, 0.800),
        (OperationType.DRILLING, MachineType.DRILLING, 0.500),
        (OperationType.GRINDING, MachineType.GRINDING, 0.432),
        (OperationType.INSPECTION, MachineType.INSPECTION, 0.300),
    ],
    "PF-05": [
        (OperationType.MILLING, MachineType.MILLING, 0.480),
        (OperationType.DRILLING, MachineType.DRILLING, 0.320),
        (OperationType.INSPECTION, MachineType.INSPECTION, 0.160),
    ],
    "PF-06": [
        (OperationType.TURNING, MachineType.CNC_LATHE, 0.450),
        (OperationType.MILLING, MachineType.MILLING, 0.520),
        (OperationType.DRILLING, MachineType.DRILLING, 0.300),
        (OperationType.INSPECTION, MachineType.INSPECTION, 0.200),
    ],
}


def _seed_orders(
    db: Session,
    rng: random.Random,
    machines: list[Machine],
    customers: list[Customer],
    families: list[PartFamily],
) -> list[ProductionOrder]:
    quantities = [
        380,
        720,
        1_250,
        2_400,
        520,
        3_600,
        950,
        1_800,
        4_800,
        640,
        2_200,
        1_150,
        3_100,
        460,
        2_750,
        880,
        1_600,
        5_000,
        780,
        2_050,
        1_380,
        3_400,
        560,
        2_600,
        1_020,
    ]
    due_offsets = [
        2,
        3,
        4,
        5,
        3,
        7,
        5,
        8,
        9,
        4,
        10,
        6,
        11,
        5,
        12,
        7,
        8,
        13,
        9,
        10,
        12,
        14,
        8,
        13,
        11,
    ]
    base_prices = {
        "PF-01": 1_180,
        "PF-02": 820,
        "PF-03": 1_460,
        "PF-04": 1_720,
        "PF-05": 540,
        "PF-06": 980,
    }
    material_by_family = {family.id: family.default_material_id for family in families}
    machines_by_type: dict[MachineType, list[Machine]] = defaultdict(list)
    for machine in machines:
        machines_by_type[machine.machine_type].append(machine)

    orders: list[ProductionOrder] = []
    for index in range(25):
        family = families[index % len(families)]
        # Tier-1 customers deliberately own more of the early, high-pressure jobs.
        customer = customers[index % 3] if index < 12 else customers[3 + index % 5]
        quantity = quantities[index]
        unit_price = float(base_prices[family.id] + (index % 5) * 45)
        material_cost = round(unit_price * (0.23 + (index % 3) * 0.025), 2)
        if index in {0, 1}:
            status = OrderStatus.COMPLETED
        elif index in {2, 3, 4, 5}:
            status = OrderStatus.IN_PROGRESS
        elif index in {6, 7, 8, 16, 17}:
            status = OrderStatus.AT_RISK
        elif index in {9, 10}:
            status = OrderStatus.DELAYED
        else:
            status = OrderStatus.PLANNED
        risk = (
            RiskLevel.CRITICAL
            if index in {7, 17}
            else RiskLevel.HIGH
            if status in {OrderStatus.AT_RISK, OrderStatus.DELAYED}
            else RiskLevel.MEDIUM
            if index in {5, 12, 21}
            else RiskLevel.LOW
        )
        due_date = datetime.combine(
            (HORIZON_START + timedelta(days=due_offsets[index])).date(), time(18, 0)
        )
        if index == 7:
            due_date = datetime(2026, 9, 3, 6, 0)
        material_available = HORIZON_START - timedelta(days=2)
        if index in {12, 17}:
            material_available = HORIZON_START + timedelta(days=4 if index == 12 else 3)
        order = ProductionOrder(
            id=f"ORD-{index + 1:03d}",
            customer_id=customer.id,
            part_family_id=family.id,
            part_number=f"{family.code}-{200 + index * 7}",
            description=f"{family.name} production batch",
            quantity=quantity,
            completed_quantity=quantity
            if status == OrderStatus.COMPLETED
            else (quantity // 3 if status == OrderStatus.IN_PROGRESS else 0),
            due_date=due_date,
            promised_date=due_date,
            status=status,
            risk_level=risk,
            priority=5
            if customer.tier == CustomerTier.TIER_1
            else 4
            if customer.tier == CustomerTier.TIER_2
            else 3,
            unit_selling_price=unit_price,
            unit_material_cost=material_cost,
            expected_production_cost=round(
                quantity * unit_price * (0.26 + (index % 4) * 0.015), 2
            ),
            late_penalty_per_day=customer.default_penalty_per_day + (index % 4) * 3_500,
            material_id=material_by_family[family.id],
            material_required_qty=round(quantity * (0.72 + (index % 5) * 0.31), 1),
            material_available_date=material_available,
            quality_reject_rate=family.typical_reject_rate,
            delivery_probability=0.58
            if risk == RiskLevel.CRITICAL
            else 0.72
            if risk == RiskLevel.HIGH
            else 0.86
            if risk == RiskLevel.MEDIUM
            else 0.96,
            expected_completion_at=None,
            notes="Material arrival requires expediting."
            if index in {12, 17}
            else None,
        )
        previous: OrderOperation | None = None
        for sequence, (operation_type, machine_type, run_rate) in enumerate(
            ROUTES[family.id], start=1
        ):
            operation = OrderOperation(
                sequence=sequence,
                operation_type=operation_type,
                required_machine_type=machine_type,
                required_skill=operation_type,
                setup_minutes=20 + ((index + sequence) % 4) * 10,
                run_minutes_per_unit=round(run_rate * (0.92 + rng.random() * 0.16), 4),
                batch_size=min(250, quantity),
                planned_quantity=quantity,
                predecessor=previous,
                outsource_allowed=operation_type == OperationType.GRINDING,
                outsource_cost_per_unit=52.0
                if operation_type == OperationType.GRINDING
                else None,
            )
            for rank, machine in enumerate(machines_by_type[machine_type], start=1):
                operation.eligible_machines.append(
                    OperationMachineEligibility(
                        machine_id=machine.id, preference_rank=rank
                    )
                )
            order.operations.append(operation)
            previous = operation
        orders.append(order)
    db.add_all(orders)
    db.flush()
    return orders


def _fit_operator_shift(
    moment: datetime, duration_minutes: int, shift_id: str
) -> datetime:
    shift_start = time(6, 0) if shift_id == "SHIFT-1" else time(14, 0)
    shift_end = time(14, 0) if shift_id == "SHIFT-1" else time(22, 0)
    candidate = moment
    while True:
        if candidate.weekday() == 6:
            candidate = datetime.combine(
                candidate.date() + timedelta(days=1), shift_start
            )
            continue
        day_start = datetime.combine(candidate.date(), shift_start)
        day_end = datetime.combine(candidate.date(), shift_end)
        candidate = max(candidate, day_start)
        if candidate + timedelta(minutes=duration_minutes) <= day_end:
            return candidate
        next_date = candidate.date() + timedelta(days=1)
        candidate = datetime.combine(next_date, shift_start)


def _fit_resource_windows(
    moment: datetime, duration_minutes: int, shift_id: str, machine: Machine
) -> datetime:
    """Fit a non-preemptive chunk around maintenance, breakdown and grid outages."""

    blocked_windows: list[tuple[datetime, datetime]] = [
        (window.start_at, window.end_at)
        for window in machine.maintenance_windows
        if window.status in {WindowStatus.PLANNED, WindowStatus.ACTIVE}
    ]
    blocked_windows.extend(
        (breakdown.start_at, breakdown.end_at)
        for breakdown in machine.breakdowns
        if breakdown.end_at is not None
    )
    # The seeded on-time plan preserves feasibility by pausing during the notified
    # grid outage; generator economics are evaluated separately by the decision API.
    blocked_windows.append((datetime(2026, 9, 3, 14, 0), datetime(2026, 9, 3, 18, 0)))
    blocked_windows.append((datetime(2026, 9, 8, 10, 0), datetime(2026, 9, 8, 12, 0)))
    candidate = _fit_operator_shift(moment, duration_minutes, shift_id)
    while True:
        end = candidate + timedelta(minutes=duration_minutes)
        overlaps = [
            blocked_end
            for blocked_start, blocked_end in blocked_windows
            if candidate < blocked_end and blocked_start < end
        ]
        if not overlaps:
            return candidate
        candidate = _fit_operator_shift(max(overlaps), duration_minutes, shift_id)


def _seed_schedules(
    db: Session,
    orders: list[ProductionOrder],
    machines: list[Machine],
    operators: list[Operator],
) -> list[Schedule]:
    metric_sets = {
        ScheduleMode.CHEAPEST: {
            "production_cost": 420_000,
            "overtime_cost": 18_000,
            "late_penalties": 95_000,
            "generator_cost": 0,
            "on_time_delivery_percent": 84.0,
            "expected_profit": 5_820_000,
            "breakdown_exposure": "HIGH",
        },
        ScheduleMode.MOST_ON_TIME: {
            "production_cost": 480_000,
            "overtime_cost": 72_000,
            "late_penalties": 10_000,
            "generator_cost": 25_000,
            "on_time_delivery_percent": 98.0,
            "expected_profit": 5_910_000,
            "breakdown_exposure": "MEDIUM",
        },
        ScheduleMode.MOST_ROBUST: {
            "production_cost": 460_000,
            "overtime_cost": 45_000,
            "late_penalties": 25_000,
            "generator_cost": 8_000,
            "on_time_delivery_percent": 95.0,
            "expected_profit": 5_940_000,
            "breakdown_exposure": "LOW",
        },
    }
    schedules: list[Schedule] = []
    for mode in ScheduleMode:
        schedule = Schedule(
            name=f"Two-week {mode.value.replace('_', ' ').title()} Plan",
            mode=mode,
            status=ScheduleStatus.ACTIVE
            if mode == ScheduleMode.MOST_ON_TIME
            else ScheduleStatus.DRAFT,
            horizon_start=HORIZON_START,
            horizon_end=HORIZON_END,
            solver_status="SEEDED_FEASIBLE",
            objective_value=float(metric_sets[mode]["expected_profit"]),
            is_valid=True,
            metrics=metric_sets[mode],
            notes="Deterministic demonstration baseline; may be regenerated by the optimizer.",
        )
        schedules.append(schedule)
    db.add_all(schedules)
    db.flush()

    active_schedule = next(
        item for item in schedules if item.mode == ScheduleMode.MOST_ON_TIME
    )
    machine_by_type: dict[MachineType, list[Machine]] = defaultdict(list)
    for machine in machines:
        machine_by_type[machine.machine_type].append(machine)
    operator_by_type: dict[MachineType, list[Operator]] = defaultdict(list)
    for operator in operators:
        for skill in operator.skills:
            if skill.certified:
                operator_by_type[skill.machine_type].append(operator)

    machine_ready = {machine.id: HORIZON_START for machine in machines}
    operator_ready = {operator.id: HORIZON_START for operator in operators}
    machine_ready["CNC-L03"] = DEMO_NOW + timedelta(hours=6, minutes=45)
    machine_ready["MILL-03"] = datetime(2026, 9, 2, 6, 0)
    operator_ready["OP-16"] = datetime(2026, 9, 2, 14, 0)
    operator_ready["OP-28"] = datetime(2026, 9, 2, 14, 0)
    machine_last_family: dict[str, str] = {}
    order_ready: dict[str, datetime] = {}
    for order in sorted(
        orders, key=lambda item: (-item.priority, item.due_date, item.id)
    ):
        if order.status == OrderStatus.COMPLETED:
            continue
        ready = max(HORIZON_START, order.material_available_date)
        for operation in order.operations:
            total_duration = max(30, operation.processing_minutes)
            remaining_minutes = total_duration
            remaining_quantity = operation.planned_quantity
            first_chunk = True
            while remaining_minutes > 0:
                duration = min(450, remaining_minutes)
                candidates: list[tuple[datetime, datetime, Machine, Operator]] = []
                for machine in machine_by_type[operation.required_machine_type]:
                    for operator in operator_by_type[operation.required_machine_type]:
                        start = max(
                            ready,
                            machine_ready[machine.id],
                            operator_ready[operator.id],
                        )
                        start = _fit_resource_windows(
                            start, duration, operator.shift_id, machine
                        )
                        end = start + timedelta(minutes=duration)
                        candidates.append((end, start, machine, operator))
                if not candidates:
                    raise RuntimeError(
                        f"No feasible machine/operator pair for {operation.operation_type}"
                    )
                end, start, machine, operator = min(
                    candidates, key=lambda item: (item[0], item[2].id, item[3].id)
                )
                if remaining_minutes == duration:
                    chunk_quantity = remaining_quantity
                else:
                    chunk_quantity = max(
                        1,
                        min(
                            remaining_quantity - 1,
                            round(
                                operation.planned_quantity * duration / total_duration
                            ),
                        ),
                    )
                previous_family = machine_last_family.get(machine.id)
                changeover_minutes = (
                    20
                    if first_chunk and previous_family == order.part_family_id
                    else 60
                    if first_chunk and previous_family
                    else 0
                )
                hours = duration / 60
                operation_status = (
                    OperationStatus.COMPLETED
                    if end <= DEMO_NOW
                    else OperationStatus.IN_PROGRESS
                    if start <= DEMO_NOW < end
                    else OperationStatus.PLANNED
                )
                active_schedule.operations.append(
                    ScheduleOperation(
                        order_operation_id=operation.id,
                        machine_id=machine.id,
                        operator_id=operator.id,
                        start_at=start,
                        end_at=end,
                        quantity=chunk_quantity,
                        status=operation_status,
                        shift_id=operator.shift_id,
                        is_overtime=False,
                        uses_generator=False,
                        changeover_minutes=changeover_minutes,
                        operation_cost=round(hours * machine.hourly_cost, 2),
                        energy_cost=round(hours * machine.power_kw * 8.4, 2),
                        labour_cost=round(hours * operator.hourly_rate, 2),
                    )
                )
                machine_ready[machine.id] = end
                operator_ready[operator.id] = end
                machine_last_family[machine.id] = order.part_family_id
                ready = end
                remaining_minutes -= duration
                remaining_quantity -= chunk_quantity
                first_chunk = False
        order_ready[order.id] = ready
        order.expected_completion_at = ready
    # A schedule is a rolling two-week window. Later operations remain in the order
    # backlog and keep their forecast completion, but are not shown outside the horizon.
    active_schedule.operations[:] = [
        operation
        for operation in active_schedule.operations
        if operation.end_at <= HORIZON_END
    ]
    return schedules


def _seed_changeovers(db: Session, families: list[PartFamily]) -> None:
    machine_types = [
        MachineType.CNC_LATHE,
        MachineType.MILLING,
        MachineType.DRILLING,
        MachineType.GRINDING,
    ]
    rows: list[ChangeoverMatrix] = []
    for from_family in families:
        for to_family in families:
            for machine_type in machine_types:
                same = from_family.id == to_family.id
                related = from_family.fixture_code[:4] == to_family.fixture_code[:4]
                minutes = 20 if same else 60 if related else 180
                rows.append(
                    ChangeoverMatrix(
                        from_part_family_id=from_family.id,
                        to_part_family_id=to_family.id,
                        machine_type=machine_type.value,
                        changeover_minutes=minutes,
                        changeover_cost=round(minutes / 60 * 1_100, 2),
                        same_fixture=same,
                    )
                )
    db.add_all(rows)


def _seed_events_and_decisions(db: Session, orders: list[ProductionOrder]) -> None:
    db.add_all(
        [
            PowerEvent(
                start_at=datetime(2026, 9, 3, 14, 0),
                end_at=datetime(2026, 9, 3, 18, 0),
                event_type=PowerEventType.PLANNED_OUTAGE,
                grid_available=False,
                generator_available=True,
                generator_capacity_kw=180.0,
                grid_cost_per_kwh=8.4,
                generator_cost_per_kwh=28.5,
                probability=0.95,
                notes="Utility feeder preventive work notice.",
            ),
            PowerEvent(
                start_at=datetime(2026, 9, 8, 10, 0),
                end_at=datetime(2026, 9, 8, 12, 0),
                event_type=PowerEventType.UNPLANNED_OUTAGE,
                grid_available=False,
                generator_available=True,
                generator_capacity_kw=180.0,
                probability=0.28,
                notes="Seasonal feeder instability scenario.",
            ),
        ]
    )
    db.add_all(
        [
            Disruption(
                disruption_type=DisruptionType.MACHINE_BREAKDOWN,
                severity=RiskLevel.CRITICAL,
                status=DisruptionStatus.OPEN,
                start_at=DEMO_NOW - timedelta(hours=1, minutes=15),
                end_at=DEMO_NOW + timedelta(hours=6, minutes=45),
                machine_id="CNC-L03",
                title="CNC-L03 servo drive trip",
                description="Machine stopped during ORD-006 turning; repair ETA is eight hours.",
                details={"repair_duration_hours": 8, "failure_code": "SERVO-07"},
                estimated_financial_impact=139_500.0,
                delivery_impact_hours=6.5,
            ),
            Disruption(
                disruption_type=DisruptionType.OPERATOR_ABSENCE,
                severity=RiskLevel.HIGH,
                status=DisruptionStatus.OPEN,
                start_at=datetime(2026, 9, 1, 14, 0),
                end_at=datetime(2026, 9, 1, 22, 0),
                operator_id="OP-28",
                title="Grinding operator unavailable",
                description="Only one certified grinding operator remains for Shift 2.",
                details={"shift_id": "SHIFT-2"},
                estimated_financial_impact=92_000.0,
                delivery_impact_hours=8.0,
            ),
            Disruption(
                disruption_type=DisruptionType.MATERIAL_DELAY,
                severity=RiskLevel.HIGH,
                status=DisruptionStatus.MITIGATING,
                start_at=DEMO_NOW - timedelta(hours=4),
                material_id="MAT-20MN",
                order_id="ORD-013",
                title="20MnCr5 arrival delayed",
                description="Supplier revised arrival by two days, blocking ORD-013 release.",
                details={"old_date": "2026-09-05", "new_date": "2026-09-07"},
                estimated_financial_impact=64_000.0,
                delivery_impact_hours=36.0,
            ),
        ]
    )
    db.flush()
    for index in (2, 7, 12, 17):
        order = orders[index]
        rejected = max(1, round(order.quantity * order.quality_reject_rate))
        db.add(
            QualityEvent(
                order_id=order.id,
                order_operation_id=order.operations[-1].id,
                detected_at=DEMO_NOW - timedelta(days=index % 4 + 1),
                inspected_quantity=order.quantity,
                rejected_quantity=rejected,
                rework_quantity=round(rejected * 0.78),
                scrap_quantity=rejected - round(rejected * 0.78),
                defect_code=f"DIM-{index + 1:02d}",
                root_cause="Fixture wear causing dimensional drift",
                rework_cost=round(rejected * 410.0, 2),
                schedule_impact_hours=round(rejected * 0.06, 1),
                closed=index < 10,
            )
        )

    recommendations = [
        Recommendation(
            category="DELIVERY",
            severity=RiskLevel.CRITICAL,
            title="Protect ORD-008 grinding slot",
            recommended_action="Approve four hours of GRIND-01 overtime on Tuesday.",
            explanation="₹21,500 overtime avoids an estimated ₹96,000 Tier-1 delivery penalty.",
            financial_benefit=96_000,
            estimated_cost=21_500,
            confidence=0.91,
            status=RecommendationStatus.PENDING,
            machine_id="GRIND-01",
            order_id="ORD-008",
            requires_approval=True,
        ),
        Recommendation(
            category="MAINTENANCE",
            severity=RiskLevel.HIGH,
            title="Advance CNC-L04 preventive maintenance",
            recommended_action="Service CNC-L04 on Saturday before the next Tier-1 batch.",
            explanation="Health is 64%; a ₹18,000 service reduces ₹1.12 lakh expected downtime exposure.",
            financial_benefit=112_000,
            estimated_cost=18_000,
            confidence=0.84,
            machine_id="CNC-L04",
            requires_approval=True,
        ),
        Recommendation(
            category="WORKFORCE",
            severity=RiskLevel.HIGH,
            title="Cross-train a fourth grinding operator",
            recommended_action="Certify OP-25 for GRIND-01 during the next low-load weekend.",
            explanation="One absence currently removes 33% of qualified grinding labour capacity.",
            financial_benefit=240_000,
            estimated_cost=45_000,
            confidence=0.88,
            machine_id="GRIND-01",
            requires_approval=True,
        ),
    ]
    db.add_all(recommendations)

    rfq = RFQ(
        id="RFQ-006",
        customer_id="CUST-01",
        customer_name="Apex Automotive Systems",
        customer_tier=CustomerTier.TIER_1,
        part_number="AXLE-490",
        part_family_id="PF-01",
        quantity=1_600,
        requested_delivery_date=datetime(2026, 9, 14, 18, 0),
        unit_selling_price=1_320.0,
        late_penalty_per_day=82_000.0,
        material_id="MAT-EN19",
        material_required_qty=2_080.0,
        material_available_date=datetime(2026, 9, 2, 6, 0),
        status=RFQStatus.ACCEPT,
        confidence=0.94,
        attractiveness_score=82.5,
        recommended_promise_date=datetime(2026, 9, 14, 18, 0),
        evaluation={
            "estimated_revenue": 2_112_000,
            "expected_production_cost": 1_430_000,
            "overtime_cost": 32_000,
            "generator_cost": 8_500,
            "expected_penalty": 5_000,
            "expected_contribution_margin": 636_500,
        },
        explanation="Capacity remains feasible with a protected Tuesday grinding slot and four overtime hours.",
    )
    for sequence, (operation, machine_type, rate) in enumerate(
        ROUTES["PF-01"], start=1
    ):
        rfq.operations.append(
            RFQOperation(
                sequence=sequence,
                operation_type=operation,
                required_machine_type=machine_type,
                setup_minutes=30,
                run_minutes_per_unit=rate,
                outsource_allowed=operation == OperationType.GRINDING,
            )
        )
    db.add(rfq)


def _seed_costs(db: Session) -> None:
    rows = [
        (
            "regular_labour_rate",
            240.0,
            "INR/hour",
            "LABOUR",
            "Blended regular operator labour rate",
        ),
        (
            "overtime_multiplier",
            1.5,
            "multiplier",
            "LABOUR",
            "Weekday overtime multiplier",
        ),
        ("sunday_multiplier", 2.0, "multiplier", "LABOUR", "Sunday labour multiplier"),
        ("electricity_price", 8.4, "INR/kWh", "ENERGY", "Industrial grid tariff"),
        (
            "generator_cost",
            28.5,
            "INR/kWh",
            "ENERGY",
            "Diesel generation variable cost",
        ),
        (
            "changeover_labour_cost",
            1_100.0,
            "INR/hour",
            "CHANGEOVER",
            "Blended setup crew and lost capacity",
        ),
        ("rework_cost", 410.0, "INR/unit", "QUALITY", "Average variable rework cost"),
        (
            "grinding_outsource_cost",
            52.0,
            "INR/unit",
            "OUTSOURCE",
            "Approved vendor grinding cost",
        ),
        (
            "generator_capacity",
            180.0,
            "kW",
            "ENERGY",
            "Available diesel generator capacity",
        ),
        (
            "reserve_capacity_target",
            0.15,
            "ratio",
            "ROBUSTNESS",
            "Target bottleneck buffer for robust plan",
        ),
    ]
    db.add_all(
        [
            CostConfiguration(
                key=key,
                value=value,
                unit=unit,
                category=category,
                description=description,
            )
            for key, value, unit, category, description in rows
        ]
    )


def seed_database(db: Session | None = None, *, force: bool = False) -> dict[str, int]:
    """Create the deterministic Sridhar Precision Works demonstration snapshot."""

    owns_session = db is None
    if force:
        Base.metadata.drop_all(bind=engine)
    init_db()
    session = db or SessionLocal()
    try:
        existing = session.scalar(select(func.count()).select_from(Machine)) or 0
        if existing:
            return {
                "machines": existing,
                "operators": session.scalar(select(func.count()).select_from(Operator))
                or 0,
                "orders": session.scalar(
                    select(func.count()).select_from(ProductionOrder)
                )
                or 0,
                "seeded": 0,
            }
        rng = random.Random(SEED)
        machines = _seed_machines(session, rng)
        operators = _seed_workforce(session, rng)
        _materials, families = _seed_materials(session)
        customers = _seed_customers(session)
        session.flush()
        orders = _seed_orders(session, rng, machines, customers, families)
        _seed_changeovers(session, families)
        _seed_schedules(session, orders, machines, operators)
        _seed_events_and_decisions(session, orders)
        _seed_costs(session)
        session.commit()
        return {"machines": 14, "operators": 40, "orders": 25, "seeded": 1}
    except Exception:
        session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the SmartForge demonstration database"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing SmartForge tables before reseeding",
    )
    args = parser.parse_args()
    result = seed_database(force=args.reset)
    print(
        f"Seed complete: {result['machines']} machines, "
        f"{result['operators']} operators, {result['orders']} orders"
    )


if __name__ == "__main__":
    main()
