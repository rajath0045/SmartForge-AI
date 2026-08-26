import { capacities, dashboard, machines, operators, orders, plans, risks, scheduleTasks } from '../data/demo';
import type {
  CapacityItem,
  ConnectionMode,
  DashboardData,
  DisruptionInput,
  Machine,
  Operator,
  Order,
  Plan,
  ReplanResult,
  RfqInput,
  RfqResult,
  RiskItem,
  ScenarioResult,
  ScheduleTask,
} from '../types';

const configuredApiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
const API_URL = (configuredApiUrl || (import.meta.env.DEV ? 'http://localhost:8000/api' : '/api')).replace(/\/$/, '');

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function unwrap<T>(payload: T | { data: T }): T {
  if (payload && typeof payload === 'object' && 'data' in payload) return payload.data;
  return payload;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 2800): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null) as { detail?: unknown } | null;
      const detail = typeof payload?.detail === 'string'
        ? payload.detail
        : Array.isArray(payload?.detail)
          ? payload.detail.map((item) => record(item).msg).filter(Boolean).join('; ')
          : '';
      throw new ApiError(response.status, detail || `Request failed (${response.status})`);
    }
    return unwrap<T>((await response.json()) as T | { data: T });
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function detectConnection(): Promise<ConnectionMode> {
  try {
    await request<unknown>('/dashboard');
    return 'live';
  } catch {
    return 'demo';
  }
}

async function withDemo<T>(remote: () => Promise<T>, local: T): Promise<T> {
  try {
    return await remote();
  } catch {
    return local;
  }
}

export const api = {
  dashboard: () => withDemo(async () => adaptDashboard(await request<unknown>('/dashboard')), dashboard),
  orders: () => withDemo(async () => adaptOrders(await request<unknown>('/orders')), orders),
  order: (id: string) => withDemo(async () => adaptOrder(await request<unknown>(`/orders/${id}`)), orders.find((order) => order.id === id) ?? orders[0]),
  machines: () => withDemo(async () => adaptMachines(await request<unknown>('/machines')), machines),
  operators: () => withDemo(async () => adaptOperators(await request<unknown>('/operators')), operators),
  risks: () => withDemo(async () => {
    const [riskPayload, recommendationPayload] = await Promise.all([
      request<unknown>('/risks'),
      request<unknown>('/recommendations').catch(() => []),
    ]);
    return adaptRisks(riskPayload, recommendationPayload);
  }, risks),
  capacity: () => withDemo(async () => adaptCapacity(await request<unknown>('/analytics/capacity')), capacities),
  schedule: () => withDemo(async () => adaptSchedule(await request<unknown>('/schedule')), scheduleTasks),
  planComparison: () => withDemo(async () => adaptPlans(await request<unknown>('/schedule/comparison', undefined, 30_000)), plans),
  evaluateRfq: async (input: RfqInput): Promise<RfqResult> => {
    try {
      return await request<RfqResult>('/rfq/evaluate', { method: 'POST', body: JSON.stringify(input) }, 20_000);
    } catch (error) {
      if (error instanceof ApiError && error.status < 500) throw error;
      return evaluateRfqLocally(input);
    }
  },
  injectDisruption: async (input: DisruptionInput): Promise<ReplanResult> => {
    try {
      return await request<ReplanResult>('/disruptions', { method: 'POST', body: JSON.stringify(input) }, 20_000);
    } catch (error) {
      if (error instanceof ApiError && error.status < 500) throw error;
      return replanLocally(input);
    }
  },
  runScenario: async (scenario: string, magnitude: number): Promise<ScenarioResult> => {
    try {
      return await request<ScenarioResult>('/simulation/run', { method: 'POST', body: JSON.stringify({ scenario, magnitude }) }, 20_000);
    } catch (error) {
      if (error instanceof ApiError && error.status < 500) throw error;
      return simulateLocally(scenario, magnitude);
    }
  },
};

type JsonRecord = Record<string, unknown>;

function record(value: unknown): JsonRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Unexpected API response');
  return value as JsonRecord;
}

function list(value: unknown): JsonRecord[] {
  if (!Array.isArray(value)) throw new Error('Unexpected API collection');
  return value.map(record);
}

function textValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function numberValue(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function isoDay(value: unknown, fallback = '2026-09-01'): string {
  const candidate = textValue(value, fallback);
  return candidate.slice(0, 10);
}

function tierValue(value: unknown): Order['tier'] {
  const normalized = textValue(value, 'TIER_2').replaceAll('_', ' ').toLowerCase();
  return normalized.includes('1') ? 'Tier 1' : normalized.includes('3') ? 'Tier 3' : 'Tier 2';
}

function humanize(value: unknown): string {
  return textValue(value).replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (character) => character.toUpperCase());
}

function adaptDashboard(payload: unknown): DashboardData {
  const source = record(payload);
  if (!source.kpis) {
    const direct = source as unknown as DashboardData;
    if (typeof direct.activeOrders === 'number') return direct;
    throw new Error('Dashboard KPIs missing');
  }
  const kpis = record(source.kpis);
  return {
    activeOrders: numberValue(kpis.activeOrders),
    completedOrders: numberValue(kpis.completedOrders),
    atRiskOrders: numberValue(kpis.ordersAtRisk),
    delayedOrders: numberValue(kpis.delayedOrders),
    onTimeDelivery: numberValue(kpis.onTimeDeliveryPercent),
    machineUtilization: numberValue(kpis.machineUtilizationPercent),
    oee: numberValue(kpis.oeePercent),
    labourUtilization: numberValue(kpis.labourUtilizationPercent),
    bottleneckUtilization: numberValue(kpis.bottleneckUtilizationPercent),
    productionCost: numberValue(kpis.productionCost),
    revenue: numberValue(kpis.revenue),
    expectedProfit: numberValue(kpis.expectedProfit),
    overtimeCost: numberValue(kpis.overtimeCost),
    latePenalties: numberValue(kpis.latePenalties),
    energyCost: numberValue(kpis.energyCost),
    generatorCost: numberValue(kpis.generatorCost),
    changeoverLoss: numberValue(kpis.changeoverLosses),
    reworkCost: numberValue(kpis.reworkCost),
  };
}

function adaptOrders(payload: unknown): Order[] {
  return list(payload).map(adaptOrderRecord);
}

function adaptOrder(payload: unknown): Order {
  return adaptOrderRecord(record(payload));
}

function adaptOrderRecord(source: JsonRecord): Order {
  if (typeof source.part === 'string' && typeof source.margin === 'number') return source as unknown as Order;
  const id = textValue(source.id, 'ORD-001');
  const local = orders.find((item) => item.id === id) ?? orders[0];
  const customer = source.customer ? record(source.customer) : {};
  const family = source.partFamily ? record(source.partFamily) : {};
  const materialDate = isoDay(source.materialAvailableDate, '2026-09-01');
  const quantity = numberValue(source.quantity, local.quantity);
  const complete = numberValue(source.completedQuantity, 0);
  const risk = textValue(source.riskLevel, local.risk) as Order['risk'];
  const status = textValue(source.status, local.status) as Order['status'];
  const operationPayload = Array.isArray(source.operations) ? list(source.operations) : [];
  const mappedOperations = operationPayload.map((operation, index) => {
    const eligible = Array.isArray(operation.eligibleMachines) ? list(operation.eligibleMachines) : [];
    const borrowed = local.operations[index];
    const operationName = humanize(operation.operationType) || borrowed?.name || `Operation ${index + 1}`;
    return {
      name: operationName,
      machine: textValue(eligible[0]?.machineId, borrowed?.machine ?? humanize(operation.requiredMachineType)),
      start: borrowed?.start ?? 'Awaiting schedule',
      end: borrowed?.end ?? 'Awaiting schedule',
      status: (index === 0 && status === 'IN_PROGRESS' ? 'RUNNING' : status === 'COMPLETED' ? 'DONE' : 'QUEUED') as Order['operations'][number]['status'],
    };
  });
  return {
    id,
    customer: textValue(customer.name, local.customer),
    tier: tierValue(customer.tier ?? local.tier),
    part: textValue(source.partNumber, local.part),
    family: textValue(family.code, local.family),
    quantity,
    completedQty: complete,
    dueDate: isoDay(source.dueDate, local.dueDate),
    expectedCompletion: isoDay(source.expectedCompletionAt, isoDay(source.promisedDate, local.expectedCompletion)),
    revenue: numberValue(source.revenue, local.revenue),
    margin: numberValue(source.expectedProfit, local.margin),
    penaltyPerDay: numberValue(source.latePenaltyPerDay, local.penaltyPerDay),
    expectedPenalty: Math.round(numberValue(source.latePenaltyPerDay, local.penaltyPerDay) * Math.max(0, 1 - numberValue(source.deliveryProbability, local.deliveryProbability / 100))),
    material: textValue(source.materialId, local.material),
    materialStatus: materialDate <= '2026-09-01' ? 'AVAILABLE' : 'INCOMING',
    status,
    risk,
    deliveryProbability: numberValue(source.deliveryProbability, local.deliveryProbability) <= 1 ? Math.round(numberValue(source.deliveryProbability) * 100) : numberValue(source.deliveryProbability),
    operations: mappedOperations.length ? mappedOperations : local.operations,
  };
}

function adaptMachines(payload: unknown): Machine[] {
  return list(payload).map((source, index) => {
    if (typeof source.type === 'string' && typeof source.utilization === 'number') return source as unknown as Machine;
    const id = textValue(source.id, machines[index]?.id);
    const local = machines.find((item) => item.id === id) ?? machines[index % machines.length];
    return {
      ...local,
      id,
      name: textValue(source.name, id),
      type: humanize(source.machineType) || local.type,
      status: textValue(source.status, local.status) as Machine['status'],
      oee: Math.round(numberValue(source.oee, local.oee) * (numberValue(source.oee, local.oee) <= 1 ? 1000 : 10)) / 10,
      healthScore: Math.round(numberValue(source.healthScore, local.healthScore)),
      mtbf: numberValue(source.mtbfHours, local.mtbf),
      mttr: numberValue(source.mttrHours, local.mttr),
      runHours: numberValue(source.totalRunningHours, local.runHours),
      lastMaintenance: isoDay(source.lastMaintenanceAt, local.lastMaintenance),
      powerKw: numberValue(source.powerKw, local.powerKw),
    };
  });
}

function adaptOperators(payload: unknown): Operator[] {
  return list(payload).map((source, index) => {
    if (source.skills && !Array.isArray(source.skills)) return source as unknown as Operator;
    const rawSkills = Array.isArray(source.skills) ? list(source.skills) : [];
    const skillMap: Operator['skills'] = { CNC: 0, Milling: 0, Drilling: 0, Grinding: 0, Inspection: 0 };
    rawSkills.forEach((skill) => {
      const operation = textValue(skill.operationType);
      const machineType = textValue(skill.machineType);
      const level = Math.max(0, Math.min(3, numberValue(skill.proficiency))) as 0 | 1 | 2 | 3;
      if (operation === 'TURNING' || machineType === 'CNC_LATHE') skillMap.CNC = Math.max(skillMap.CNC, level) as 0 | 1 | 2 | 3;
      else if (operation === 'MILLING') skillMap.Milling = Math.max(skillMap.Milling, level) as 0 | 1 | 2 | 3;
      else if (operation === 'DRILLING') skillMap.Drilling = Math.max(skillMap.Drilling, level) as 0 | 1 | 2 | 3;
      else if (operation === 'GRINDING') skillMap.Grinding = Math.max(skillMap.Grinding, level) as 0 | 1 | 2 | 3;
      else if (operation === 'INSPECTION') skillMap.Inspection = Math.max(skillMap.Inspection, level) as 0 | 1 | 2 | 3;
    });
    const rawShift = source.shift ? record(source.shift) : {};
    const shiftName = textValue(rawShift.name);
    const status = textValue(source.status, 'AVAILABLE');
    return {
      id: textValue(source.id, `OP-${index + 1}`),
      name: textValue(source.name, `Operator ${index + 1}`),
      shift: shiftName.toLowerCase().includes('2') ? 'Shift 2' : 'Shift 1',
      experience: numberValue(source.experienceYears),
      status: status === 'AVAILABLE' ? 'PRESENT' : status === 'LEAVE' ? 'LEAVE' : 'ABSENT',
      overtimeEligible: Boolean(source.overtimeEligible),
      skills: skillMap,
    };
  });
}

function adaptRisks(payload: unknown, recommendationsPayload: unknown): RiskItem[] {
  const recommendations = Array.isArray(recommendationsPayload) ? list(recommendationsPayload) : [];
  return list(payload).map((source, index) => {
    if (typeof source.financialImpact === 'number') return source as unknown as RiskItem;
    const recommendation = recommendations.find((item) => textValue(item.machineId) === textValue(source.machineId) || textValue(item.orderId) === textValue(source.orderId)) ?? recommendations[index];
    const rawCategory = textValue(source.category);
    const category: RiskItem['category'] = rawCategory.includes('MACHINE') ? 'MACHINE' : rawCategory.includes('OPERATOR') ? 'LABOUR' : rawCategory.includes('MATERIAL') ? 'MATERIAL' : rawCategory.includes('POWER') ? 'POWER' : rawCategory.includes('QUALITY') ? 'QUALITY' : rawCategory.includes('CAPACITY') ? 'CAPACITY' : 'DELIVERY';
    const affected = [source.machineId, source.operatorId, source.orderId, source.materialId].map((item) => textValue(item)).filter(Boolean);
    const probability = numberValue(source.probability, 0.5);
    const startAt = textValue(source.startAt);
    return {
      id: textValue(source.id, `RSK-${index + 1}`),
      title: textValue(source.title, 'Factory exception'),
      category,
      severity: textValue(source.severity, 'MEDIUM') as RiskItem['severity'],
      probability: probability <= 1 ? Math.round(probability * 100) : Math.round(probability),
      financialImpact: numberValue(source.estimatedFinancialImpact),
      deliveryImpact: `${numberValue(source.deliveryImpactHours).toFixed(1)} hours delivery impact`,
      affected: affected.length ? affected : ['Plant 01'],
      detected: startAt ? new Date(startAt).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Current horizon',
      recommendation: textValue(recommendation?.recommendedAction, 'Open the control center and evaluate the least-cost recovery action.'),
      rationale: textValue(recommendation?.explanation, textValue(source.description, 'Compare recovery cost with protected contribution and penalty exposure.')),
      status: textValue(source.status) === 'MITIGATING' ? 'MONITORING' : recommendation?.requiresApproval ? 'APPROVAL_REQUIRED' : 'OPEN',
      future: startAt ? new Date(startAt).getTime() > new Date('2026-09-01T12:00:00').getTime() : false,
    };
  });
}

function adaptCapacity(payload: unknown): CapacityItem[] {
  if (Array.isArray(payload)) return list(payload) as unknown as CapacityItem[];
  const source = record(payload);
  const machineRows = Array.isArray(source.byMachine) ? list(source.byMachine) : [];
  const typeRows = Array.isArray(source.byMachineType) ? list(source.byMachineType) : [];
  const combined = [...machineRows, ...typeRows];
  if (!combined.length) throw new Error('Capacity rows missing');
  return combined.map((item) => {
    const available = numberValue(item.availableHours);
    const committed = numberValue(item.committedHours);
    const utilization = numberValue(item.utilizationPercent, available ? committed / available * 100 : 0);
    return {
      resource: textValue(item.machineId, humanize(item.machineType)),
      type: item.machineId ? 'Machine' : 'Operation',
      available,
      committed,
      predicted: Math.min(available * 1.15, committed * (utilization > 88 ? 1.03 : 1.06)),
      unit: 'h',
      status: utilization >= 92 ? 'CRITICAL' : utilization >= 80 ? 'WATCH' : 'HEALTHY',
    };
  });
}

function adaptSchedule(payload: unknown): ScheduleTask[] {
  if (Array.isArray(payload)) return list(payload) as unknown as ScheduleTask[];
  const source = record(payload);
  const horizon = new Date(textValue(source.horizonStart, '2026-09-01T06:00:00'));
  const operationRows = Array.isArray(source.operations) ? list(source.operations) : [];
  if (!operationRows.length) throw new Error('Schedule operations missing');
  return operationRows.map((operation, index) => {
    const start = new Date(textValue(operation.startAt));
    const day = Math.max(0, Math.min(13, Math.floor((start.getTime() - horizon.getTime()) / 86_400_000)));
    const status = textValue(operation.status);
    return {
      id: textValue(operation.id, `TASK-${index + 1}`),
      machineId: textValue(operation.machineId),
      orderId: textValue(operation.orderId),
      operation: humanize(operation.operationType),
      tier: tierValue(operation.customerTier),
      day,
      startHour: start.getHours() + start.getMinutes() / 60,
      duration: numberValue(operation.durationMinutes) / 60,
      kind: status === 'SETUP' ? 'CHANGEOVER' : 'PRODUCTION',
      status: status === 'COMPLETED' ? 'DONE' : status === 'IN_PROGRESS' ? 'RUNNING' : status === 'BLOCKED' ? 'AT_RISK' : 'PLANNED',
    };
  });
}

function adaptPlans(payload: unknown): Plan[] {
  if (Array.isArray(payload)) return payload as Plan[];
  const source = record(payload);
  const rows = Array.isArray(source.plans) ? list(source.plans) : [];
  if (!rows.length) throw new Error('Plan comparison missing');
  const recommendedMode = textValue(source.recommendedMode, 'MOST_ROBUST');
  return rows.map((row) => {
    const mode = textValue(row.mode);
    const id: Plan['id'] = mode === 'CHEAPEST' ? 'cheapest' : mode === 'MOST_ON_TIME' ? 'ontime' : 'robust';
    const local = plans.find((item) => item.id === id)!;
    return {
      ...local,
      id,
      name: textValue(row.name, local.name),
      productionCost: numberValue(row.productionCost, local.productionCost),
      overtime: numberValue(row.overtimeCost, local.overtime),
      penalties: numberValue(row.latePenalties, local.penalties),
      generatorCost: numberValue(row.generatorCost, local.generatorCost),
      onTimeDelivery: numberValue(row.onTimeDeliveryPercent, local.onTimeDelivery),
      expectedProfit: numberValue(row.expectedProfit, local.expectedProfit),
      breakdownExposure: textValue(row.breakdownExposure, local.breakdownExposure) as Plan['breakdownExposure'],
      breakdownExposureCost: numberValue(row.breakdownExposureCost, local.breakdownExposureCost),
      recommended: mode === recommendedMode,
    };
  }).sort((left, right) => ['cheapest', 'ontime', 'robust'].indexOf(left.id) - ['cheapest', 'ontime', 'robust'].indexOf(right.id));
}

function daysUntil(date: string): number {
  const target = new Date(`${date}T18:00:00`);
  const baseline = new Date('2026-09-01T06:00:00');
  return Math.max(1, Math.ceil((target.getTime() - baseline.getTime()) / 86_400_000));
}

export function evaluateRfqLocally(input: RfqInput): RfqResult {
  const quantityFactor = input.quantity / 1000;
  const operationHours: Record<string, number> = { Turning: 5.2, Milling: 4.8, Drilling: 2.4, Grinding: 6.4, Inspection: 1.2 };
  const totalHours = input.operations.reduce((sum, op) => sum + (operationHours[op] ?? 3), 0) * quantityFactor;
  const grindingHours = input.operations.includes('Grinding') ? operationHours.Grinding * quantityFactor : 0;
  const availableDays = daysUntil(input.requestedDate);
  const dailyCapacity = input.operations.includes('Grinding') ? 2.8 : 14;
  const loadAfter = Math.min(132, 96.2 + (grindingHours / 160) * 100);
  const feasibleRegularHours = availableDays * dailyCapacity;
  const materialDelayDays = input.materialAvailable ? 0 : 2;
  const regularFeasible = totalHours <= feasibleRegularHours && loadAfter <= 101 && materialDelayDays < availableDays;
  const overtimeHours = regularFeasible ? 0 : Math.max(0, Math.min(20, totalHours - feasibleRegularHours));
  const unitRevenue = input.sellingPrice > 10_000 ? input.sellingPrice : input.sellingPrice * input.quantity;
  const revenue = Math.max(unitRevenue, input.quantity * 280);
  const baseProductionCost = revenue * (input.tier === 'Tier 1' ? 0.66 : 0.62);
  const overtimeCost = Math.round(overtimeHours * 1_250);
  const generatorNeeded = availableDays <= 4 && input.operations.includes('Grinding');
  const generatorCost = generatorNeeded ? Math.round(Math.min(8, grindingHours) * 3_500) : 0;
  const delayDays = Math.max(0, Math.ceil((totalHours - feasibleRegularHours - overtimeHours) / Math.max(1, dailyCapacity)) + materialDelayDays);
  const expectedPenalty = Math.round(delayDays * input.latePenalty * (input.tier === 'Tier 1' ? 0.88 : 0.62));
  const riskCost = Math.round(revenue * (input.operations.includes('Grinding') ? 0.035 : 0.018));
  const contributionMargin = Math.round(revenue - baseProductionCost - overtimeCost - generatorCost - expectedPenalty - riskCost);
  const score = Math.round(Math.max(0, Math.min(100, 52 + (contributionMargin / Math.max(revenue, 1)) * 100 - Math.max(0, loadAfter - 95) * 1.4 + (input.tier === 'Tier 1' ? 9 : 3))));

  let decision: RfqResult['decision'] = 'ACCEPT';
  if (contributionMargin < 0 || loadAfter > 124) decision = 'REJECT';
  else if (loadAfter > 112) decision = 'OUTSOURCE BOTTLENECK OPERATION';
  else if (delayDays > 1) decision = 'ACCEPT WITH NEGOTIATED DELIVERY DATE';
  else if (generatorNeeded && generatorCost < Math.max(input.latePenalty, contributionMargin * 0.2)) decision = 'ACCEPT WITH GENERATOR USAGE';
  else if (overtimeHours > 0) decision = 'ACCEPT WITH OVERTIME';

  const confidence = Math.round(Math.max(48, Math.min(97, 96 - Math.max(0, loadAfter - 92) * 1.2 - materialDelayDays * 5 - delayDays * 7)));
  const recommended = new Date(`${input.requestedDate}T12:00:00`);
  if (decision === 'ACCEPT WITH NEGOTIATED DELIVERY DATE') recommended.setDate(recommended.getDate() + Math.max(2, delayDays));

  return {
    decision,
    confidence,
    score,
    requestedDate: input.requestedDate,
    recommendedDate: recommended.toISOString().slice(0, 10),
    revenue: Math.round(revenue),
    productionCost: Math.round(baseProductionCost),
    overtimeCost,
    generatorCost,
    expectedPenalty,
    contributionMargin,
    bottleneckLoad: Math.round(loadAfter * 10) / 10,
    reasons: [
      `The routing consumes an estimated ${totalHours.toFixed(1)} finite-capacity hours, including ${grindingHours.toFixed(1)} hours on GRIND-01.`,
      decision === 'REJECT'
        ? `Risk-adjusted economics do not protect existing commitments: projected contribution is ${contributionMargin < 0 ? 'negative' : 'below the capacity hurdle'}.`
        : `Projected contribution remains positive after labour, reliability, overtime, power and penalty exposure.`,
      input.tier === 'Tier 1'
        ? 'Strategic customer weight improves sequence priority, but the recommendation still passes the contribution and capacity checks.'
        : 'Existing Tier-1 commitments remain protected before this order is inserted.',
    ],
    capacityChecks: [
      { label: 'Machine capacity', value: `${Math.max(0, feasibleRegularHours - totalHours).toFixed(1)} h slack`, state: loadAfter > 110 ? 'CRITICAL' : loadAfter > 98 ? 'HIGH' : 'LOW' },
      { label: 'Grinding bottleneck', value: `${loadAfter.toFixed(1)}% projected`, state: loadAfter > 110 ? 'CRITICAL' : loadAfter > 98 ? 'HIGH' : 'MEDIUM' },
      { label: 'Qualified labour', value: input.operations.includes('Grinding') ? '2 of 3 available' : 'Roster covered', state: input.operations.includes('Grinding') ? 'MEDIUM' : 'LOW' },
      { label: 'Material', value: input.materialAvailable ? 'Available' : '2-day lead time', state: input.materialAvailable ? 'LOW' : 'HIGH' },
    ],
  };
}

function replanLocally(input: DisruptionInput): ReplanResult {
  const factor = Math.max(1, input.durationHours);
  const breakdown = input.type === 'MACHINE_BREAKDOWN';
  const power = input.type === 'POWER_CUT';
  const costPerHour = breakdown ? 17_400 : power ? 12_600 : input.type === 'QUALITY_REWORK' ? 9_800 : 7_200;
  const penaltyIncrease = Math.round(factor * (breakdown ? 9_375 : power ? 6_200 : 4_100));
  const overtime = Math.min(12, Math.ceil(factor * (breakdown ? 0.55 : 0.35)));
  return {
    disruptionCost: Math.round(factor * costPerHour + penaltyIncrease + overtime * 1_250),
    jobsMoved: Math.ceil(factor / 2) + 3,
    machineChanges: breakdown ? 2 : 0,
    shiftChanges: Math.ceil(factor / 4) + 1,
    newOvertimeHours: overtime,
    newGeneratorHours: power ? Math.min(8, factor) : 0,
    ordersAtRisk: factor >= 6 ? ['ORD-018', 'ORD-021'] : ['ORD-018'],
    penaltyIncrease,
    lostProduction: Math.round(factor * (breakdown ? 42 : 31)),
    ownerCall: {
      contact: breakdown ? 'Ravi Grinding Services' : power ? 'TNEB Control Room + DG contractor' : 'Apex Driveline planning desk',
      reason: breakdown
        ? 'Reserve a 5.5-hour grinding slot; ₹34K outsourcing protects ₹1.65L Tier-1 penalty exposure.'
        : power
          ? 'Confirm outage restoration while selective generator operation protects the critical shipment.'
          : 'Agree sequence and revised dispatch before downstream commitments are affected.',
    },
    changes: [
      { order: 'ORD-018', operation: 'Grinding', before: 'Wed · Shift 2 · GRIND-01', after: 'Tue · OT · GRIND-01', impact: '+4 h overtime' },
      { order: 'ORD-021', operation: 'Grinding', before: 'Tue · Shift 2 · GRIND-01', after: 'Thu · Shift 1 · GRIND-01', impact: '+16 h completion' },
      { order: 'ORD-014', operation: 'Grinding', before: 'Thu · Shift 1 · GRIND-01', after: 'Outsource · Ravi Grinding', impact: '+₹34,000' },
      { order: 'ORD-004', operation: 'Inspection', before: 'Thu · Shift 2', after: 'Fri · Shift 1', impact: '+8 h completion' },
    ],
    explanation: `Completed work is frozen. Remaining operations were resequenced around ${input.resource}; the replanner protects ORD-018 first because its ₹76,000/day Tier-1 penalty exceeds the overtime and outsourcing recovery cost.`,
    valid: true,
    status: 'FEASIBLE',
    violations: [],
  };
}

function simulateLocally(scenario: string, magnitude: number): ScenarioResult {
  const baseline = { delivery: 92.6, revenue: 8_640_000, cost: 5_810_000, profit: 2_180_000, penalties: 164_000, overtime: 128_000, utilization: 78.4, load: 96.2 };
  const positive = scenario === 'cross-train' || scenario === 'new-grinder' || scenario === 'sunday-overtime' || scenario === 'outsource';
  const severity = Math.max(1, magnitude);
  const deliveryDelta = (positive ? 0.9 : -1.15) * Math.sqrt(severity);
  const costDelta = scenario === 'new-grinder' ? 2_800_000 : positive ? 18_000 * severity : 31_000 * severity;
  const penaltyDelta = positive ? -12_000 * severity : 18_500 * severity;
  const profitDelta = -costDelta - penaltyDelta + (scenario === 'new-grinder' ? 3_140_000 : positive ? 24_000 * severity : 0);
  return {
    label: scenario.replaceAll('-', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
    delivery: Math.max(55, Math.min(99.5, baseline.delivery + deliveryDelta)),
    revenue: baseline.revenue,
    cost: baseline.cost + costDelta,
    profit: baseline.profit + profitDelta,
    penalties: Math.max(0, baseline.penalties + penaltyDelta),
    overtime: baseline.overtime + (scenario === 'sunday-overtime' ? 32_000 * severity : positive ? 4_000 * severity : 11_000 * severity),
    utilization: Math.max(35, Math.min(100, baseline.utilization + (positive ? -0.8 : 1.3) * severity)),
    bottleneckLoad: Math.max(62, Math.min(125, baseline.load + (positive ? -1.8 : 2.2) * severity)),
    baseline: {
      delivery: baseline.delivery,
      revenue: baseline.revenue,
      cost: baseline.cost,
      profit: baseline.profit,
      penalties: baseline.penalties,
      overtime: baseline.overtime,
      utilization: baseline.utilization,
      bottleneckLoad: baseline.load,
    },
    valid: true,
    status: 'FEASIBLE',
    violations: [],
    recommendation: positive
      ? 'This intervention improves protected throughput; proceed if the stated one-time cost is within the approved envelope.'
      : 'Use the robust plan and approve the targeted recovery action before accepting additional grinding demand.',
  };
}
