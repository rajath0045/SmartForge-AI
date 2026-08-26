import { useMemo, useState } from 'react';
import { ArrowRight, BatteryCharging, Bolt, Check, CircleDollarSign, CircleGauge, Factory, Fuel, Lightbulb, ShieldCheck, Sun, TrendingDown, TrendingUp, Zap } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { capacities as fallbackCapacities, dashboard as fallbackDashboard, energyTrend, orders, plans as fallbackPlans } from '../data/demo';
import { useAsyncData } from '../hooks';
import { api } from '../services/api';
import type { Plan } from '../types';
import { Badge, KpiCard, MetricRow, money, PageHeader, Panel, Progress, SeverityBadge } from '../components/UI';
import { SegmentedTabs } from '../components/SegmentedTabs';

const tooltip = { background: '#172733', border: '1px solid #2d4657', borderRadius: 8, color: '#fff', fontSize: 12 };

export function CapacityPage() {
  const { data: capacities } = useAsyncData(api.capacity, fallbackCapacities);
  const [view, setView] = useState<'all' | 'Machine' | 'Skill'>('all');
  const shown = capacities.filter((item) => view === 'all' || item.type === view);
  return (
    <div className="page-stack">
      <PageHeader kicker="AVAILABLE-TO-PROMISE INPUT" title="Capacity planning" description="Available, committed and predicted capacity by machine, operation and critical skill for the two-week horizon." actions={<SegmentedTabs label="Capacity view" value={view} onChange={setView} items={[{ value: 'all', label: 'All', count: capacities.length }, { value: 'Machine', label: 'Machines' }, { value: 'Skill', label: 'Skills' }]} />} />
      <div className="capacity-hero">
        <Panel className="constraint-panel">
          <div className="constraint-top"><div><span className="eyebrow">CURRENT PRODUCTION CONSTRAINT</span><h2>GRIND-01</h2><p>Cylindrical grinding · 8 dependent orders</p></div><Badge tone="critical" dot>CRITICAL</Badge></div>
          <div className="constraint-number"><strong>96.2%</strong><span>committed load</span></div><Progress value={96.2} label="Capacity consumed" />
          <div className="four-metrics"><div><span>Available</span><strong>160 h</strong></div><div><span>Committed</span><strong>154 h</strong></div><div><span>Free</span><strong>6 h</strong></div><div><span>Queue</span><strong>42 h</strong></div></div>
        </Panel>
        <Panel title="Constraint economics" eyebrow="THEORY OF CONSTRAINTS">
          <div className="constraint-money"><span>Revenue dependent on GRIND-01</span><strong>₹34.8L</strong><small>4 Tier-1 orders · ₹4.1L penalty exposure</small></div>
          <div className="resource-list"><MetricRow label="1 protected grinder hour" value="₹18,400 contribution" /><MetricRow label="Target reserve" value="19.2 hours" /><MetricRow label="Current reserve" value="6.0 hours" tone="critical" /><MetricRow label="Gap to target" value="13.2 hours" /></div>
          <p className="explain-box"><Lightbulb />Outsource 5.5 hours and approve one overtime shift. This restores 11.8 hours reserve for a net expected benefit of ₹1.31L.</p>
        </Panel>
      </div>
      <Panel className="flush-panel" title="Resource capacity" eyebrow="14-DAY HORIZON">
        <div className="capacity-list">{shown.map((item) => {
          const used = item.committed / item.available * 100;
          return <div className="capacity-row" key={item.resource}><div className="capacity-name"><span className={`capacity-icon status-${item.status.toLowerCase()}`}><Factory /></span><div><strong>{item.resource}</strong><small>{item.type} · {item.unit}</small></div></div><div className="capacity-bars"><div className="capacity-labels"><span>Committed <strong>{item.committed}</strong></span><span>Predicted <strong>{item.predicted}</strong></span><span>Available <strong>{item.available}</strong></span></div><div className="dual-progress"><span className={`committed status-${item.status.toLowerCase()}`} style={{ width: `${Math.min(100, used)}%` }} /><span className="predicted" style={{ left: `${Math.min(98, item.predicted / item.available * 100)}%` }} /></div></div><div className="capacity-free"><strong>{Math.max(0, item.available - item.committed).toFixed(0)}</strong><span>{item.unit} free</span></div><Badge tone={item.status}>{item.status}</Badge></div>;
        })}</div>
      </Panel>
      <Panel className="recommendation-strip"><ShieldCheck /><div><strong>Order acceptance guardrail</strong><p>Do not promise additional grinding demand before 08 Sep unless it uses overtime, outsourcing, or a negotiated delivery date. The RFQ engine reads this same capacity ledger.</p></div><a className="button button-secondary" href="/acceptance">Evaluate RFQ <ArrowRight /></a></Panel>
    </div>
  );
}

export function EnergyPage() {
  const [approved, setApproved] = useState(false);
  const generatorCost = 28_000;
  const avoidedPenalty = 115_000;
  return (
    <div className="page-stack">
      <PageHeader kicker="ENERGY-AWARE SCHEDULING" title="Energy & power" description="Schedule economically through grid interruptions; run the generator only when protected margin and penalties justify it." actions={<Badge tone="healthy" dot>GRID STABLE NOW</Badge>} />
      <div className="kpi-grid kpi-grid-4 compact-kpis"><KpiCard label="Grid energy" value="1,486 kWh" detail="₹9.10 / kWh blended" icon={<Bolt />} /><KpiCard label="Peak demand" value="126 kW" detail="At 10:20 today" icon={<CircleGauge />} /><KpiCard label="Generator use" value="8.0 h" detail="Planned Thursday outage" tone="warning" icon={<Fuel />} /><KpiCard label="Energy cost" value="₹2.76L" detail="4.8% of production cost" icon={<CircleDollarSign />} /></div>
      <div className="dashboard-grid">
        <Panel className="span-8" title="Power availability and machine load" eyebrow="TODAY · kW">
          <div className="chart-lg"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={energyTrend} margin={{ top: 10, right: 12, left: -10 }}><CartesianGrid stroke="#e7ecef" strokeDasharray="3 4" vertical={false} /><XAxis dataKey="hour" axisLine={false} tickLine={false} tick={{ fontSize: 11 }} /><YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11 }} /><Tooltip contentStyle={tooltip} /><Area type="monotone" dataKey="grid" stackId="power" fill="#52748b" stroke="#415f73" fillOpacity={0.75} /><Area type="monotone" dataKey="generator" stackId="power" fill="#d08a2e" stroke="#c27b22" fillOpacity={0.8} /><Line type="monotone" dataKey="load" stroke="#172733" strokeWidth={2.5} dot={false} /><ReferenceLine x="14:00" stroke="#ad554c" strokeDasharray="4 3" label={{ value: 'Outage window', fill: '#ad554c', fontSize: 10 }} /></ComposedChart></ResponsiveContainer></div>
          <div className="chart-legend"><span><i style={{ background: '#52748b' }} />Grid</span><span><i style={{ background: '#d08a2e' }} />Generator</span><span><i style={{ background: '#172733' }} />Machine load</span></div>
        </Panel>
        <Panel className="span-4 generator-decision" title="Thursday outage" eyebrow="14:00–18:00 · PLANNED" action={<Badge tone="high">DECISION DUE</Badge>}>
          <div className="energy-choice"><span className="energy-choice-icon"><BatteryCharging /></span><div><small>RECOMMENDATION</small><strong>Run generator selectively</strong><p>Power GRIND-01, MILL-01 and inspection only.</p></div></div>
          <div className="economics-versus"><div><span>Generator cost</span><strong>{money(generatorCost, false)}</strong></div><span>vs</span><div><span>Penalty avoided</span><strong>{money(avoidedPenalty, false)}</strong></div></div>
          <div className="decision-net"><span>Expected net protection</span><strong>{money(avoidedPenalty - generatorCost, false)}</strong></div>
          <p className="explain-box"><Zap />Do not run non-critical machines: their ₹18K fuel cost would avoid only ₹7.5K of delay exposure.</p>
          <button className={`button full-button ${approved ? 'button-success' : 'button-primary'}`} onClick={() => setApproved(true)}>{approved ? <><Check />Generator plan approved</> : 'Approve selective generator plan'}</button>
        </Panel>
      </div>
      <Panel title="Machine energy intensity" eyebrow="kWh PER PRODUCTIVE HOUR">
        <div className="energy-machine-grid">{[
          ['GRIND-01', 22, 18400], ['MILL-01', 18, 12600], ['MILL-02', 18, 11800], ['CNC-L03', 16, 9400], ['CNC-L01', 14, 10400], ['DRILL-01', 8, 6800],
        ].map(([name, kw, value]) => <div key={name}><span><strong>{name}</strong><small>₹{Number(value).toLocaleString('en-IN')} contribution / h</small></span><div className="energy-bar"><i style={{ width: `${Number(kw) / 22 * 100}%` }} /></div><strong>{kw} kW</strong></div>)}</div>
      </Panel>
    </div>
  );
}

export function ProfitabilityPage() {
  const { data: financials } = useAsyncData(api.dashboard, fallbackDashboard);
  const [metric, setMetric] = useState<'margin' | 'revenue'>('margin');
  const ranked = useMemo(() => [...orders].sort((a, b) => b[metric] - a[metric]).slice(0, 10), [metric]);
  const waterfall = [
    { name: 'Revenue', value: 8640, color: '#52748b' }, { name: 'Material', value: -2880, color: '#ad554c' }, { name: 'Operations', value: -2170, color: '#ad554c' }, { name: 'Labour', value: -930, color: '#ad554c' }, { name: 'Energy', value: -318, color: '#ad554c' }, { name: 'Risk cost', value: -164, color: '#ad554c' }, { name: 'Profit', value: 2178, color: '#588064' },
  ];
  return (
    <div className="page-stack">
      <PageHeader kicker="RISK-ADJUSTED ECONOMICS" title="Profitability & cost" description="Expected commercial result after material, operations, labour, energy, changeovers, rework and delivery risk." actions={<button className="button button-secondary" onClick={() => window.print()}>Export cost brief</button>} />
      <div className="kpi-grid kpi-grid-5"><KpiCard label="Revenue" value={money(financials.revenue)} trend={4.2} trendLabel="current horizon" icon={<TrendingUp />} /><KpiCard label="Expected profit" value={money(financials.expectedProfit)} trend={6.8} trendLabel={`${(financials.expectedProfit / Math.max(1, financials.revenue) * 100).toFixed(1)}% margin`} tone="profit" icon={<CircleDollarSign />} /><KpiCard label="Penalty exposure" value={money(financials.latePenalties)} trend={-12.5} trendLabel="Lower is better" tone="danger" icon={<TrendingDown />} /><KpiCard label="Rework cost" value={money(financials.reworkCost)} detail="Expected quality loss" icon={<Factory />} /><KpiCard label="Changeover loss" value={money(financials.changeoverLoss)} detail="Sequence-dependent setups" icon={<CircleGauge />} /></div>
      <div className="dashboard-grid">
        <Panel className="span-8" title="Expected profit bridge" eyebrow="₹ THOUSANDS"><div className="chart-lg"><ResponsiveContainer width="100%" height="100%"><BarChart data={waterfall} margin={{ top: 16, left: 4, right: 8 }}><CartesianGrid stroke="#e7ecef" strokeDasharray="3 4" vertical={false} /><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11 }} /><YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11 }} /><Tooltip contentStyle={tooltip} formatter={(value) => `${Number(value) < 0 ? '−' : ''}₹${Math.abs(Number(value)).toLocaleString('en-IN')}K`} /><Bar dataKey="value" radius={[4, 4, 0, 0]}>{waterfall.map((item) => <Cell key={item.name} fill={item.color} />)}</Bar></BarChart></ResponsiveContainer></div></Panel>
        <Panel className="span-4" title="Margin quality" eyebrow="WHAT CHANGED"><div className="profit-driver good"><TrendingUp /><span><strong>+₹1.18L</strong><small>Better part-family sequencing reduced changeovers</small></span></div><div className="profit-driver bad"><TrendingDown /><span><strong>−₹68.5K</strong><small>PF-04 rework consumed 6.5 capacity hours</small></span></div><div className="profit-driver bad"><TrendingDown /><span><strong>−₹42K</strong><small>Generator recovery during prior outage</small></span></div><p className="explain-box"><Lightbulb />Protecting one extra GRIND-01 hour yields more contribution than optimizing four low-load drill hours.</p></Panel>
      </div>
      <Panel className="flush-panel">
        <div className="table-toolbar"><div className="table-title"><h2>Order economics</h2><Badge tone="neutral">Top 10</Badge></div><SegmentedTabs label="Order economics ranking" value={metric} onChange={setMetric} items={[{ value: 'margin', label: 'By contribution' }, { value: 'revenue', label: 'By revenue' }]} /></div>
        <div className="table-scroll"><table><thead><tr><th>Order</th><th>Customer</th><th>Revenue</th><th>Contribution</th><th>Penalty risk</th><th>Margin after risk</th><th>Delivery</th></tr></thead><tbody>{ranked.map((order) => <tr key={order.id}><td><strong>{order.id}</strong><small>{order.part}</small></td><td>{order.customer}<small>{order.tier}</small></td><td>{money(order.revenue)}</td><td className="text-healthy">{money(order.margin)}</td><td>{money(order.expectedPenalty)}</td><td><strong>{money(order.margin - order.expectedPenalty)}</strong></td><td><Badge tone={order.risk}>{order.deliveryProbability}%</Badge></td></tr>)}</tbody></table></div>
      </Panel>
    </div>
  );
}

export function PlanComparisonPage() {
  const { data: plans } = useAsyncData(api.planComparison, fallbackPlans);
  const [selected, setSelected] = useState<Plan['id']>('robust');
  const selectedPlan = plans.find((plan) => plan.id === selected)!;
  const recommendedPlan = plans.find((plan) => plan.recommended) ?? plans.find((plan) => plan.id === 'robust') ?? plans[0];
  const cheapestPlan = plans.find((plan) => plan.id === 'cheapest') ?? plans[0];
  const profitSacrifice = Math.max(0, cheapestPlan.expectedProfit - recommendedPlan.expectedProfit);
  const exposureReduction = Math.max(0, (cheapestPlan.breakdownExposureCost ?? 0) - (recommendedPlan.breakdownExposureCost ?? 0));
  return (
    <div className="page-stack comparison-page">
      <PageHeader kicker="MULTI-OBJECTIVE OPTIMIZATION" title="Compare three valid production plans" description="Each plan satisfies hard feasibility constraints. The difference is how it values cost, due dates and disruption reserve." actions={<Badge tone="healthy"><Check />CONSTRAINTS VALIDATED</Badge>} />
      <div className="plan-cards">{plans.map((plan) => <button key={plan.id} className={`plan-card plan-${plan.id} ${selected === plan.id ? 'selected' : ''}`} onClick={() => setSelected(plan.id)}><div className="plan-card-top"><span className="plan-radio">{selected === plan.id && <Check />}</span><div><small>{plan.id === recommendedPlan.id ? 'RECOMMENDED' : 'ALTERNATIVE'}</small><h2>{plan.name}</h2></div>{plan.id === recommendedPlan.id && <Badge tone="healthy">BEST BALANCE</Badge>}</div><p>{plan.description}</p><div className="plan-hero"><span><small>Expected profit</small><strong>{money(plan.expectedProfit)}</strong></span><span><small>On-time</small><strong>{plan.onTimeDelivery}%</strong></span></div><div className="plan-mini-metrics"><span>Penalty <strong>{money(plan.penalties)}</strong></span><span>Reserve <strong>{plan.reserveCapacity}%</strong></span><span>Risk <SeverityBadge level={plan.breakdownExposure} /></span></div></button>)}</div>
      <Panel className="flush-panel" title="Trade-off matrix" eyebrow="CURRENT TWO-WEEK HORIZON">
        <div className="table-scroll"><table className="comparison-table"><thead><tr><th>Metric</th>{plans.map((plan) => <th key={plan.id} className={selected === plan.id ? 'selected-col' : ''}>{plan.name}{plan.id === recommendedPlan.id && <small>Recommended</small>}</th>)}</tr></thead><tbody>{[
          ['Production cost', (p: Plan) => money(p.productionCost)], ['Overtime', (p: Plan) => money(p.overtime)], ['Late penalties', (p: Plan) => money(p.penalties)], ['Generator cost', (p: Plan) => money(p.generatorCost)], ['Changeovers', (p: Plan) => `${p.changeovers} events`], ['On-time delivery', (p: Plan) => `${p.onTimeDelivery}%`], ['Expected profit', (p: Plan) => money(p.expectedProfit)], ['Breakdown exposure', (p: Plan) => p.breakdownExposure], ['Reserve capacity', (p: Plan) => `${p.reserveCapacity}%`],
        ].map(([label, getter]) => <tr key={String(label)}><td>{String(label)}</td>{plans.map((plan) => <td key={plan.id} className={selected === plan.id ? 'selected-col' : ''}><strong>{(getter as (p: Plan) => string)(plan)}</strong></td>)}</tr>)}</tbody></table></div>
      </Panel>
      <Panel className="plan-recommendation"><div className="recommendation-emblem"><ShieldCheck /></div><div><span className="eyebrow">MANAGEMENT RECOMMENDATION</span><h2>Use the {recommendedPlan.name} plan</h2><p>It preserves {recommendedPlan.onTimeDelivery.toFixed(1)}% on-time delivery while pricing fragile-machine exposure and bottleneck reserve. The modeled reliability protection is worth more than fully loading GRIND-01 for the lowest nominal cost.</p><div className="recommendation-math"><span>Profit sacrifice <strong>{money(profitSacrifice)}</strong></span><ArrowRight /><span>Risk exposure reduced <strong>{exposureReduction ? money(exposureReduction) : recommendedPlan.breakdownExposure}</strong></span><ArrowRight /><span>Protected reserve <strong>{recommendedPlan.reserveCapacity}%</strong></span></div></div><button className="button button-primary" onClick={(event) => { event.currentTarget.textContent = `${selectedPlan.name} activated`; }}>Activate {selectedPlan.name}</button></Panel>
    </div>
  );
}
