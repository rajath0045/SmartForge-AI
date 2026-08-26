export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type MachineStatus = 'RUNNING' | 'IDLE' | 'SETUP' | 'MAINTENANCE' | 'BREAKDOWN';
export type OrderStatus = 'PLANNED' | 'IN_PROGRESS' | 'AT_RISK' | 'DELAYED' | 'COMPLETED';
export type Tier = 'Tier 1' | 'Tier 2' | 'Tier 3';

export interface DashboardData {
  activeOrders: number;
  completedOrders: number;
  atRiskOrders: number;
  delayedOrders: number;
  onTimeDelivery: number;
  machineUtilization: number;
  oee: number;
  labourUtilization: number;
  bottleneckUtilization: number;
  revenue: number;
  expectedProfit: number;
  productionCost: number;
  overtimeCost: number;
  latePenalties: number;
  energyCost: number;
  generatorCost: number;
  changeoverLoss: number;
  reworkCost: number;
}

export interface OrderOperation {
  name: string;
  machine: string;
  start: string;
  end: string;
  status: 'DONE' | 'RUNNING' | 'QUEUED' | 'BLOCKED';
}

export interface Order {
  id: string;
  customer: string;
  tier: Tier;
  part: string;
  family: string;
  quantity: number;
  completedQty: number;
  dueDate: string;
  expectedCompletion: string;
  revenue: number;
  margin: number;
  penaltyPerDay: number;
  expectedPenalty: number;
  material: string;
  materialStatus: 'AVAILABLE' | 'INCOMING' | 'SHORTAGE';
  status: OrderStatus;
  risk: RiskLevel;
  deliveryProbability: number;
  operations: OrderOperation[];
}

export interface Machine {
  id: string;
  name: string;
  type: string;
  status: MachineStatus;
  currentOrder?: string;
  utilization: number;
  oee: number;
  healthScore: number;
  mtbf: number;
  mttr: number;
  runHours: number;
  lastMaintenance: string;
  nextMaintenance: string;
  qualifiedOperators: number;
  queueHours: number;
  powerKw: number;
}

export interface Operator {
  id: string;
  name: string;
  shift: 'Shift 1' | 'Shift 2';
  experience: number;
  status: 'PRESENT' | 'ABSENT' | 'LEAVE';
  overtimeEligible: boolean;
  skills: Record<'CNC' | 'Milling' | 'Drilling' | 'Grinding' | 'Inspection', 0 | 1 | 2 | 3>;
}

export interface RiskItem {
  id: string;
  title: string;
  category: 'DELIVERY' | 'MACHINE' | 'LABOUR' | 'MATERIAL' | 'POWER' | 'QUALITY' | 'CAPACITY';
  severity: RiskLevel;
  probability: number;
  financialImpact: number;
  deliveryImpact: string;
  affected: string[];
  detected: string;
  recommendation: string;
  rationale: string;
  status: 'OPEN' | 'MONITORING' | 'APPROVAL_REQUIRED' | 'MITIGATED';
  future?: boolean;
}

export interface ScheduleTask {
  id: string;
  machineId: string;
  orderId: string;
  operation: string;
  tier: Tier;
  day: number;
  startHour: number;
  duration: number;
  kind: 'PRODUCTION' | 'CHANGEOVER' | 'MAINTENANCE' | 'BREAKDOWN';
  status: 'DONE' | 'RUNNING' | 'PLANNED' | 'AT_RISK';
}

export interface RfqInput {
  customer: string;
  tier: Tier;
  part: string;
  quantity: number;
  requestedDate: string;
  sellingPrice: number;
  latePenalty: number;
  operations: string[];
  materialAvailable: boolean;
}

export type RfqDecision = 'ACCEPT' | 'ACCEPT WITH OVERTIME' | 'ACCEPT WITH GENERATOR USAGE' | 'ACCEPT WITH NEGOTIATED DELIVERY DATE' | 'ACCEPT WITH PARTIAL DELIVERY' | 'OUTSOURCE BOTTLENECK OPERATION' | 'REJECT';

export interface RfqResult {
  decision: RfqDecision;
  confidence: number;
  score: number;
  requestedDate: string;
  recommendedDate: string;
  revenue: number;
  productionCost: number;
  overtimeCost: number;
  generatorCost: number;
  expectedPenalty: number;
  contributionMargin: number;
  bottleneckLoad: number;
  reasons: string[];
  capacityChecks: Array<{ label: string; value: string; state: RiskLevel }>;
}

export interface CapacityItem {
  resource: string;
  type: 'Machine' | 'Skill' | 'Operation';
  available: number;
  committed: number;
  predicted: number;
  unit: string;
  status: 'HEALTHY' | 'WATCH' | 'CRITICAL';
}

export interface Plan {
  id: 'cheapest' | 'ontime' | 'robust';
  name: string;
  productionCost: number;
  overtime: number;
  penalties: number;
  generatorCost: number;
  changeovers: number;
  onTimeDelivery: number;
  expectedProfit: number;
  breakdownExposure: RiskLevel;
  breakdownExposureCost?: number;
  reserveCapacity: number;
  description: string;
  recommended?: boolean;
}

export interface DisruptionInput {
  type: 'MACHINE_BREAKDOWN' | 'OPERATOR_ABSENCE' | 'MATERIAL_DELAY' | 'QUALITY_REWORK' | 'POWER_CUT';
  resource: string;
  start: string;
  durationHours: number;
  notes: string;
}

export interface ReplanResult {
  disruptionCost: number;
  jobsMoved: number;
  machineChanges: number;
  shiftChanges: number;
  newOvertimeHours: number;
  newGeneratorHours: number;
  ordersAtRisk: string[];
  penaltyIncrease: number;
  lostProduction: number;
  ownerCall: { contact: string; reason: string };
  changes: Array<{ order: string; operation: string; before: string; after: string; impact: string }>;
  explanation: string;
  valid?: boolean;
  status?: string;
  violations?: Array<{ code: string; message: string }>;
}

export interface ScenarioResult {
  label: string;
  delivery: number;
  revenue: number;
  cost: number;
  profit: number;
  penalties: number;
  overtime: number;
  utilization: number;
  bottleneckLoad: number;
  recommendation: string;
  baseline?: {
    delivery: number;
    revenue: number;
    cost: number;
    profit: number;
    penalties: number;
    overtime: number;
    utilization: number;
    bottleneckLoad: number;
  };
  valid?: boolean;
  status?: string;
  violations?: Array<{ code: string; message: string }>;
}

export type ConnectionMode = 'checking' | 'live' | 'demo';
