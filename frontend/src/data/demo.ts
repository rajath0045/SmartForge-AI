import type {
  CapacityItem,
  DashboardData,
  Machine,
  Operator,
  Order,
  Plan,
  RiskItem,
  ScheduleTask,
} from '../types';

export const dashboard: DashboardData = {
  activeOrders: 25,
  completedOrders: 47,
  atRiskOrders: 3,
  delayedOrders: 1,
  onTimeDelivery: 92.6,
  machineUtilization: 78.4,
  oee: 74.8,
  labourUtilization: 82.1,
  bottleneckUtilization: 96.2,
  revenue: 8_640_000,
  expectedProfit: 2_180_000,
  productionCost: 5_810_000,
  overtimeCost: 128_000,
  latePenalties: 164_000,
  energyCost: 276_000,
  generatorCost: 42_000,
  changeoverLoss: 71_500,
  reworkCost: 68_500,
};

const machineRows: Array<[string, string, Machine['status'], number, number, number, number, number, number, number]> = [
  ['CNC-L01', 'CNC Lathe', 'RUNNING', 84, 81, 88, 620, 2.1, 12, 14],
  ['CNC-L02', 'CNC Lathe', 'RUNNING', 79, 78, 91, 710, 1.8, 8, 14],
  ['CNC-L03', 'CNC Lathe', 'SETUP', 72, 74, 76, 480, 3.2, 17, 16],
  ['CNC-L04', 'CNC Lathe', 'IDLE', 64, 70, 82, 560, 2.7, 5, 15],
  ['CNC-L05', 'CNC Lathe', 'MAINTENANCE', 58, 68, 69, 410, 4.1, 6, 15],
  ['MILL-01', 'VMC Milling', 'RUNNING', 88, 79, 84, 530, 2.5, 18, 18],
  ['MILL-02', 'VMC Milling', 'RUNNING', 83, 76, 80, 490, 3.0, 15, 18],
  ['MILL-03', 'VMC Milling', 'IDLE', 69, 73, 87, 650, 2.2, 7, 17],
  ['DRILL-01', 'Drilling', 'RUNNING', 75, 77, 90, 730, 1.4, 9, 8],
  ['DRILL-02', 'Drilling', 'RUNNING', 71, 75, 86, 680, 1.6, 7, 8],
  ['DRILL-03', 'Drilling', 'IDLE', 62, 72, 92, 790, 1.2, 4, 8],
  ['GRIND-01', 'Cyl. Grinding', 'RUNNING', 96, 71, 61, 350, 5.8, 42, 22],
  ['INSPECT-01', 'Quality Inspection', 'RUNNING', 78, 83, 93, 900, 0.8, 11, 3],
  ['INSPECT-02', 'Quality Inspection', 'IDLE', 66, 80, 95, 980, 0.6, 6, 3],
];

export const machines: Machine[] = machineRows.map((row, index) => ({
  id: row[0],
  name: row[0],
  type: row[1],
  status: row[2],
  currentOrder: row[2] === 'RUNNING' ? `ORD-${String(((index * 3) % 24) + 1).padStart(3, '0')}` : undefined,
  utilization: row[3],
  oee: row[4],
  healthScore: row[5],
  mtbf: row[6],
  mttr: row[7],
  runHours: 2200 + index * 287,
  lastMaintenance: `2026-08-${String(3 + (index % 15)).padStart(2, '0')}`,
  nextMaintenance: `2026-09-${String(2 + (index % 19)).padStart(2, '0')}`,
  qualifiedOperators: row[0] === 'GRIND-01' ? 3 : 5 + (index % 4),
  queueHours: row[8],
  powerKw: row[9],
}));

const customerNames = ['Apex Driveline', 'Kaveri Motors', 'Nexon Brakes', 'Vector Auto', 'Rane Mobility', 'Sundaram Axles', 'Indus Motion', 'Aster Components'];
const parts = ['AX-204', 'GB-118', 'BR-420', 'SH-208', 'SP-331', 'CL-509', 'PN-744', 'HU-166'];
const routes = [
  ['Turning', 'Milling', 'Grinding', 'Inspection'],
  ['Turning', 'Drilling', 'Inspection'],
  ['Milling', 'Drilling', 'Grinding', 'Inspection'],
  ['Turning', 'Milling', 'Inspection'],
];

export const orders: Order[] = Array.from({ length: 25 }, (_, index) => {
  const n = index + 1;
  const tier = (n % 5 === 0 ? 'Tier 3' : n % 3 === 0 ? 'Tier 2' : 'Tier 1') as Order['tier'];
  const risk = (n === 18 ? 'CRITICAL' : n === 14 || n === 21 ? 'HIGH' : n % 7 === 0 ? 'MEDIUM' : 'LOW') as Order['risk'];
  const status = (n === 14 ? 'DELAYED' : risk === 'CRITICAL' || risk === 'HIGH' ? 'AT_RISK' : n % 4 === 0 ? 'PLANNED' : 'IN_PROGRESS') as Order['status'];
  const qty = 320 + ((n * 347) % 4100);
  const revenue = 280_000 + ((n * 137_000) % 1_180_000);
  const route = routes[index % routes.length];
  const dueDay = 2 + (n % 14);
  const dueDate = `2026-09-${String(dueDay).padStart(2, '0')}`;
  const completionOffset = risk === 'CRITICAL' ? 2 : risk === 'HIGH' ? 1 : -1;
  const completionDay = dueDay + completionOffset;
  const expectedCompletion = `2026-09-${String(completionDay).padStart(2, '0')}`;
  const id = `ORD-${String(n).padStart(3, '0')}`;
  return {
    id,
    customer: customerNames[index % customerNames.length],
    tier,
    part: parts[index % parts.length],
    family: `PF-${String((index % 6) + 1).padStart(2, '0')}`,
    quantity: qty,
    completedQty: status === 'PLANNED' ? 0 : Math.floor(qty * (0.18 + (index % 6) * 0.1)),
    dueDate,
    expectedCompletion,
    revenue,
    margin: Math.round(revenue * (0.18 + (index % 4) * 0.025)),
    penaltyPerDay: tier === 'Tier 1' ? 76_000 + index * 950 : tier === 'Tier 2' ? 28_000 + index * 500 : 9_000 + index * 240,
    expectedPenalty: risk === 'CRITICAL' ? 152_000 : risk === 'HIGH' ? 62_000 : status === 'DELAYED' ? 78_000 : 0,
    material: index % 3 === 0 ? 'EN8 Round Bar' : index % 3 === 1 ? 'EN24 Forging' : 'SG Iron Casting',
    materialStatus: n === 14 ? 'SHORTAGE' : n === 9 || n === 22 ? 'INCOMING' : 'AVAILABLE',
    status,
    risk,
    deliveryProbability: risk === 'CRITICAL' ? 62 : risk === 'HIGH' ? 74 : risk === 'MEDIUM' ? 86 : 96 - (index % 4),
    operations: route.map((op, opIndex) => ({
      name: op,
      machine: op === 'Turning' ? `CNC-L0${(index % 5) + 1}` : op === 'Milling' ? `MILL-0${(index % 3) + 1}` : op === 'Drilling' ? `DRILL-0${(index % 3) + 1}` : op === 'Grinding' ? 'GRIND-01' : `INSPECT-0${(index % 2) + 1}`,
      start: `2026-09-${String(1 + Math.min(4, opIndex + (index % 3))).padStart(2, '0')} ${opIndex % 2 ? '14:00' : '06:00'}`,
      end: `2026-09-${String(1 + Math.min(4, opIndex + (index % 3))).padStart(2, '0')} ${opIndex % 2 ? '18:20' : '11:30'}`,
      status: opIndex === 0 && status !== 'PLANNED' ? 'DONE' : opIndex === 1 && status === 'IN_PROGRESS' ? 'RUNNING' : risk === 'CRITICAL' && op === 'Grinding' ? 'BLOCKED' : 'QUEUED',
    })),
  };
});

const operatorNames = ['Arun K.', 'Bhaskar R.', 'Chandru M.', 'Deepa S.', 'Elango P.', 'Farooq A.', 'Gita N.', 'Hari V.', 'Indira R.', 'Jagan P.', 'Karthik S.', 'Lakshmi M.', 'Manoj T.', 'Naveen K.', 'Omkar D.', 'Priya R.', 'Qadir S.', 'Revathi P.', 'Senthil M.', 'Tharani V.'];

export const operators: Operator[] = Array.from({ length: 40 }, (_, index) => {
  const grindQualified = index === 2 || index === 14 || index === 31;
  return {
    id: `OP-${String(index + 1).padStart(2, '0')}`,
    name: operatorNames[index % operatorNames.length] + (index >= operatorNames.length ? ' II' : ''),
    shift: index % 2 === 0 ? 'Shift 1' : 'Shift 2',
    experience: 2 + (index % 13),
    status: index === 14 ? 'ABSENT' : index === 27 ? 'LEAVE' : 'PRESENT',
    overtimeEligible: index % 5 !== 0,
    skills: {
      CNC: index % 3 === 0 || index % 3 === 1 ? ((index % 3) + 1) as 1 | 2 | 3 : 0,
      Milling: index % 4 === 0 || index % 4 === 1 ? ((index % 3) + 1) as 1 | 2 | 3 : 0,
      Drilling: index % 5 === 0 || index % 5 === 2 ? ((index % 3) + 1) as 1 | 2 | 3 : 0,
      Grinding: grindQualified ? (index === 2 ? 3 : 2) : 0,
      Inspection: index % 7 === 0 || index % 7 === 3 ? ((index % 3) + 1) as 1 | 2 | 3 : 0,
    },
  };
});

export const risks: RiskItem[] = [
  {
    id: 'RSK-101', title: 'Tier-1 shipment may miss dispatch', category: 'DELIVERY', severity: 'CRITICAL', probability: 68,
    financialImpact: 165_000, deliveryImpact: 'ORD-018 +1.8 days', affected: ['ORD-018', 'GRIND-01'], detected: '08:42 today',
    recommendation: 'Approve 4 hours grinding overtime Tuesday Shift 2.',
    rationale: '₹21,500 overtime protects ₹1.65L expected penalty and a ₹9.4L strategic shipment.', status: 'APPROVAL_REQUIRED',
  },
  {
    id: 'RSK-102', title: 'Grinding queue exceeds protected capacity', category: 'CAPACITY', severity: 'HIGH', probability: 86,
    financialImpact: 118_000, deliveryImpact: '3 orders exposed', affected: ['GRIND-01', 'ORD-018', 'ORD-021'], detected: '07:30 today',
    recommendation: 'Move ORD-021 to Tuesday Shift 2 and outsource 5.5 hours of ORD-014.',
    rationale: 'Queue is 42 hours against 36 hours usable capacity; outsourcing costs ₹34K versus ₹1.18L exposure.', status: 'OPEN',
  },
  {
    id: 'RSK-103', title: 'EN8 material arrival delayed', category: 'MATERIAL', severity: 'HIGH', probability: 100,
    financialImpact: 78_000, deliveryImpact: 'ORD-014 blocked 1 day', affected: ['ORD-014'], detected: 'Yesterday 17:20',
    recommendation: 'Expedite 1.2 tonnes from alternate supplier before 16:00.',
    rationale: '₹18K expedite premium is below ₹78K likely penalty.', status: 'OPEN',
  },
  {
    id: 'RSK-104', title: 'CNC-L03 vibration trend elevated', category: 'MACHINE', severity: 'MEDIUM', probability: 41,
    financialImpact: 56_000, deliveryImpact: '6 hours potential downtime', affected: ['CNC-L03', 'ORD-007'], detected: '06:15 today',
    recommendation: 'Inspect spindle during Saturday maintenance window.',
    rationale: 'Planned inspection costs ₹8K; expected unplanned loss is ₹23K risk-adjusted.', status: 'MONITORING', future: true,
  },
  {
    id: 'RSK-105', title: 'Single qualified grinder operator on Shift 2', category: 'LABOUR', severity: 'HIGH', probability: 72,
    financialImpact: 92_000, deliveryImpact: 'Wednesday Shift 2 uncovered', affected: ['OP-15', 'GRIND-01'], detected: 'Roster projection',
    recommendation: 'Move OP-03 to Shift 2 and approve transport allowance.',
    rationale: '₹1,800 allowance protects 7.5 productive grinding hours.', status: 'APPROVAL_REQUIRED', future: true,
  },
  {
    id: 'RSK-106', title: 'Planned outage overlaps critical grinding', category: 'POWER', severity: 'HIGH', probability: 90,
    financialImpact: 115_000, deliveryImpact: 'Thursday 14:00–18:00', affected: ['ORD-004', 'GRIND-01'], detected: 'TNEB notice',
    recommendation: 'Run generator for GRIND-01 and MILL-01 only.',
    rationale: '₹28K generator cost avoids ₹1.15L penalty; non-critical machines should remain off.', status: 'APPROVAL_REQUIRED', future: true,
  },
  {
    id: 'RSK-107', title: 'PF-04 first-pass yield below target', category: 'QUALITY', severity: 'MEDIUM', probability: 57,
    financialImpact: 44_000, deliveryImpact: '6.5 rework hours forecast', affected: ['ORD-009', 'ORD-017'], detected: 'Weekly quality review',
    recommendation: 'Add first-off inspection after turning for PF-04.',
    rationale: '₹6.5K inspection cost is forecast to prevent ₹44K rework.', status: 'MONITORING', future: true,
  },
];

export const capacities: CapacityItem[] = [
  { resource: 'GRIND-01', type: 'Machine', available: 160, committed: 154, predicted: 157, unit: 'h', status: 'CRITICAL' },
  { resource: 'VMC Milling', type: 'Operation', available: 480, committed: 412, predicted: 428, unit: 'h', status: 'WATCH' },
  { resource: 'CNC Lathes', type: 'Operation', available: 800, committed: 546, predicted: 574, unit: 'h', status: 'HEALTHY' },
  { resource: 'Drilling', type: 'Operation', available: 480, committed: 326, predicted: 344, unit: 'h', status: 'HEALTHY' },
  { resource: 'Inspection', type: 'Operation', available: 320, committed: 244, predicted: 259, unit: 'h', status: 'WATCH' },
  { resource: 'Grinding skill', type: 'Skill', available: 112, committed: 108, predicted: 110, unit: 'operator h', status: 'CRITICAL' },
  { resource: 'CNC skill', type: 'Skill', available: 488, committed: 351, predicted: 372, unit: 'operator h', status: 'HEALTHY' },
  { resource: 'Milling skill', type: 'Skill', available: 288, committed: 236, predicted: 248, unit: 'operator h', status: 'WATCH' },
];

export const plans: Plan[] = [
  { id: 'cheapest', name: 'Cheapest Plan', productionCost: 4_220_000, overtime: 18_000, penalties: 95_000, generatorCost: 0, changeovers: 19, onTimeDelivery: 84, expectedProfit: 2_310_000, breakdownExposure: 'HIGH', reserveCapacity: 3, description: 'Clusters part families and avoids premium shifts; accepts calculated lateness on flexible orders.' },
  { id: 'ontime', name: 'Most On-Time', productionCost: 4_810_000, overtime: 72_000, penalties: 10_000, generatorCost: 25_000, changeovers: 25, onTimeDelivery: 98, expectedProfit: 2_240_000, breakdownExposure: 'MEDIUM', reserveCapacity: 5, description: 'Protects due dates with overtime and selective generator use, especially for Tier-1 commitments.' },
  { id: 'robust', name: 'Most Robust', productionCost: 4_590_000, overtime: 45_000, penalties: 25_000, generatorCost: 8_000, changeovers: 21, onTimeDelivery: 95, expectedProfit: 2_290_000, breakdownExposure: 'LOW', reserveCapacity: 14, description: 'Keeps capacity buffers around GRIND-01 and high-risk machines to absorb disruptions.' },
];

const productionMachines = machines.map((machine) => machine.id);
export const scheduleTasks: ScheduleTask[] = Array.from({ length: 62 }, (_, index) => {
  const machineId = productionMachines[index % productionMachines.length];
  const day = (index * 3 + Math.floor(index / 14)) % 14;
  const kind = (index % 19 === 0 ? 'MAINTENANCE' : index % 11 === 0 ? 'CHANGEOVER' : 'PRODUCTION') as ScheduleTask['kind'];
  return {
    id: `TASK-${index + 1}`,
    machineId,
    orderId: `ORD-${String(((index * 7) % 25) + 1).padStart(3, '0')}`,
    operation: kind === 'CHANGEOVER' ? 'Changeover' : kind === 'MAINTENANCE' ? 'Planned maintenance' : machines[index % machines.length].type.includes('Grinding') ? 'Grinding' : machines[index % machines.length].type.includes('Milling') ? 'Milling' : machines[index % machines.length].type.includes('Drilling') ? 'Drilling' : machines[index % machines.length].type.includes('Inspection') ? 'Inspection' : 'Turning',
    tier: (index % 4 === 0 ? 'Tier 2' : index % 9 === 0 ? 'Tier 3' : 'Tier 1') as ScheduleTask['tier'],
    day,
    startHour: index % 2 === 0 ? 0.5 : 8.5,
    duration: kind === 'CHANGEOVER' ? 1.5 : kind === 'MAINTENANCE' ? 4 : 5 + (index % 3),
    kind,
    status: index < 5 ? 'DONE' : index === 17 ? 'AT_RISK' : index === 4 ? 'RUNNING' : 'PLANNED',
  };
});

export const throughputTrend = [
  { day: 'Mon', planned: 890, actual: 862, risk: 46 },
  { day: 'Tue', planned: 940, actual: 928, risk: 34 },
  { day: 'Wed', planned: 910, actual: 881, risk: 68 },
  { day: 'Thu', planned: 980, actual: 952, risk: 54 },
  { day: 'Fri', planned: 870, actual: 854, risk: 42 },
  { day: 'Sat', planned: 620, actual: 604, risk: 28 },
  { day: 'Sun', planned: 180, actual: 175, risk: 18 },
];

export const costBreakdown = [
  { name: 'Material', value: 2_880_000, color: '#334e68' },
  { name: 'Machine', value: 1_240_000, color: '#52748b' },
  { name: 'Labour', value: 930_000, color: '#d08a2e' },
  { name: 'Energy', value: 318_000, color: '#6d8f72' },
  { name: 'Risk cost', value: 442_000, color: '#ad554c' },
];

export const energyTrend = [
  { hour: '06:00', grid: 86, generator: 0, load: 82 },
  { hour: '08:00', grid: 112, generator: 0, load: 107 },
  { hour: '10:00', grid: 126, generator: 0, load: 121 },
  { hour: '12:00', grid: 94, generator: 0, load: 90 },
  { hour: '14:00', grid: 62, generator: 38, load: 96 },
  { hour: '16:00', grid: 58, generator: 42, load: 97 },
  { hour: '18:00', grid: 108, generator: 0, load: 104 },
  { hour: '20:00', grid: 76, generator: 0, load: 71 },
];
