import { useMemo, useState } from 'react';
import { useReducedMotion } from 'motion/react';
import { Activity, AlertTriangle, ArrowRight, CalendarClock, Check, CircleGauge, GraduationCap, Search, ShieldCheck, UserCheck, UsersRound, Wrench } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { machines as fallbackMachines, operators as fallbackOperators } from '../data/demo';
import { useAsyncData } from '../hooks';
import { api } from '../services/api';
import type { Machine, Operator } from '../types';
import { Badge, KpiCard, MetricRow, PageHeader, Panel, Progress } from '../components/UI';

const chartTooltip = { background: '#172733', border: '1px solid #2d4657', borderRadius: 8, color: '#fff', fontSize: 12 };

export function MachinesPage() {
  const { data: machines } = useAsyncData(api.machines, fallbackMachines);
  const [selectedId, setSelectedId] = useState(fallbackMachines[0]?.id ?? 'GRIND-01');
  const [filter, setFilter] = useState('ALL');
  const reduceMotion = useReducedMotion();
  const bottleneck = useMemo(() => machines.reduce((highest, machine) => machine.utilization > highest.utilization ? machine : highest, machines[0]), [machines]);
  const selected = machines.find((machine) => machine.id === selectedId) ?? machines[0];
  const shown = machines.filter((machine) => filter === 'ALL' || machine.status === filter);
  function openBottleneck() {
    setFilter('ALL');
    setSelectedId(bottleneck.id);
    window.requestAnimationFrame(() => {
      const detail = document.getElementById('machine-detail');
      detail?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
      detail?.focus({ preventScroll: true });
    });
  }
  return (
    <div className="page-stack">
      <PageHeader kicker="EQUIPMENT DIGITAL TWIN" title="Machines" description="Current state, loading and operating context for all 14 finite-capacity resources." actions={<button className="button button-primary" aria-controls="machine-detail" onClick={openBottleneck}>Open {bottleneck.id} bottleneck <ArrowRight /></button>} />
      <div className="machine-status-overview">
        {(['RUNNING', 'IDLE', 'SETUP', 'MAINTENANCE', 'BREAKDOWN'] as const).map((status) => <button key={status} className={filter === status ? 'active' : ''} onClick={() => setFilter(filter === status ? 'ALL' : status)}><Badge tone={status} dot>{status}</Badge><strong>{machines.filter((machine) => machine.status === status).length}</strong></button>)}
      </div>
      <div className="assets-layout">
        <Panel className="machine-list-panel flush-panel">
          <div className="machine-grid">{shown.map((machine) => <button key={machine.id} className={`machine-card ${selected.id === machine.id ? 'selected' : ''}`} onClick={() => setSelectedId(machine.id)}><div className="machine-card-head"><span className={`machine-glyph health-${machine.healthScore < 70 ? 'critical' : machine.healthScore < 82 ? 'warning' : 'healthy'}`}><Wrench /></span><Badge tone={machine.status} dot>{machine.status}</Badge></div><h3>{machine.id}</h3><p>{machine.type}</p><div className="machine-running"><span>{machine.currentOrder ?? 'No active job'}</span><strong>{machine.utilization}% load</strong></div><Progress value={machine.utilization} /><div className="machine-foot"><span>OEE <strong>{machine.oee}%</strong></span><span>Health <strong>{machine.healthScore}</strong></span></div></button>)}</div>
        </Panel>
        <Panel id="machine-detail" tabIndex={-1} className={`machine-detail ${selected.id === bottleneck.id ? 'bottleneck-selected' : ''}`} eyebrow={selected.id === bottleneck.id ? 'BOTTLENECK RESOURCE DETAIL' : 'RESOURCE DETAIL'} title={selected.id} action={<Badge tone={selected.healthScore < 70 ? 'critical' : selected.healthScore < 82 ? 'warning' : 'healthy'}>{selected.healthScore}/100 HEALTH</Badge>}>
          <div className="detail-machine-state"><span className={`machine-big-icon health-${selected.healthScore < 70 ? 'critical' : selected.healthScore < 82 ? 'warning' : 'healthy'}`}><Wrench /></span><div><small>CURRENT STATE</small><strong>{selected.status}</strong><span>{selected.currentOrder ? `${selected.currentOrder} in process` : 'Available for dispatch'}</span></div></div>
          <div className="detail-gauges"><div><span>14-day load</span><strong>{selected.utilization}%</strong><Progress value={selected.utilization} /></div><div><span>Simplified OEE</span><strong>{selected.oee}%</strong><Progress value={selected.oee} tone="normal" /></div></div>
          <div className="resource-list"><MetricRow label="Queue waiting" value={`${selected.queueHours} hours`} tone={selected.queueHours > 30 ? 'critical' : undefined} /><MetricRow label="Qualified operators" value={String(selected.qualifiedOperators)} /><MetricRow label="Power draw" value={`${selected.powerKw} kW`} /><MetricRow label="Total running hours" value={selected.runHours.toLocaleString('en-IN')} /><MetricRow label="MTBF / MTTR" value={`${selected.mtbf} h / ${selected.mttr} h`} /><MetricRow label="Next maintenance" value={selected.nextMaintenance} /></div>
          {selected.id === 'GRIND-01' && <div className="machine-recommendation"><AlertTriangle /><div><strong>Protect the constraint</strong><p>Keep 12% reserve capacity and do not place flexible Tier-3 work ahead of ORD-018.</p></div></div>}
          <button className="button button-secondary full-button" onClick={() => window.alert(`Maintenance work order prepared for ${selected.id}.`)}>Prepare maintenance work order</button>
        </Panel>
      </div>
    </div>
  );
}

export function MachineHealthPage() {
  const { data: machines } = useAsyncData(api.machines, fallbackMachines);
  const sorted = [...machines].sort((a, b) => a.healthScore - b.healthScore);
  return (
    <div className="page-stack">
      <PageHeader kicker="RULE-BASED PREDICTIVE MAINTENANCE" title="Machine health" description="Transparent risk scoring from hours since service, failure frequency, MTBF and recent downtime—no black-box failure claims." actions={<button className="button button-secondary" onClick={() => window.print()}>Maintenance brief</button>} />
      <div className="kpi-grid kpi-grid-4 compact-kpis"><KpiCard label="Fleet health" value="83 / 100" detail="Weighted by criticality" icon={<Activity />} /><KpiCard label="Needs attention" value={String(machines.filter((machine) => machine.healthScore < 82).length)} detail="Under 82 health score" tone="danger" icon={<AlertTriangle />} /><KpiCard label="Planned this month" value="4" detail="18.5 maintenance hours" icon={<CalendarClock />} /><KpiCard label="Avoided risk cost" value="₹2.1L" detail="Expected-value estimate" icon={<ShieldCheck />} /></div>
      <div className="dashboard-grid">
        <Panel className="span-8" title="Fleet health ranking" eyebrow="LOWEST SCORE FIRST">
          <div className="chart-xl"><ResponsiveContainer width="100%" height="100%"><BarChart data={sorted} layout="vertical" margin={{ left: 6, right: 30 }}><CartesianGrid stroke="#e7ecef" strokeDasharray="3 4" horizontal={false} /><XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="id" width={76} axisLine={false} tickLine={false} tick={{ fontSize: 11 }} /><Tooltip contentStyle={chartTooltip} formatter={(value) => `${value}/100`} /><Bar dataKey="healthScore" radius={[0, 4, 4, 0]}>{sorted.map((machine) => <Cell key={machine.id} fill={machine.healthScore < 70 ? '#ad554c' : machine.healthScore < 82 ? '#d08a2e' : '#588064'} />)}</Bar></BarChart></ResponsiveContainer></div>
        </Panel>
        <Panel className="span-4" title="How the score works" eyebrow="EXPLAINABLE MODEL">
          <div className="score-formula"><div><span>35%</span><p>Hours since maintenance vs service interval</p></div><div><span>30%</span><p>Failure count and recent downtime</p></div><div><span>20%</span><p>MTBF trend relative to machine family</p></div><div><span>15%</span><p>Current load and critical-order exposure</p></div></div>
          <p className="explain-box"><CircleGauge />A low score is a decision signal, not a failure prediction. Maintenance is recommended only when expected avoided loss exceeds planned downtime cost.</p>
        </Panel>
      </div>
      <Panel className="flush-panel" title="Maintenance priorities" eyebrow="NEXT 30 DAYS">
        <div className="table-scroll"><table><thead><tr><th>Machine</th><th>Health</th><th>MTBF</th><th>Last service</th><th>Risk basis</th><th>Recommended window</th><th>Action</th></tr></thead><tbody>{sorted.slice(0, 7).map((machine) => <tr key={machine.id}><td><strong>{machine.id}</strong><small>{machine.type}</small></td><td><Badge tone={machine.healthScore < 70 ? 'critical' : machine.healthScore < 82 ? 'warning' : 'healthy'}>{machine.healthScore}/100</Badge></td><td>{machine.mtbf} h</td><td>{machine.lastMaintenance}</td><td>{machine.healthScore < 70 ? 'High load + shortening MTBF' : machine.healthScore < 82 ? 'Service interval approaching' : 'Routine interval'}<small>MTTR {machine.mttr} h</small></td><td>{machine.id === 'GRIND-01' ? 'Sat 05 Sep · 14:00' : machine.nextMaintenance}</td><td><button className="button button-small button-secondary" onClick={(event) => { event.currentTarget.textContent = 'Planned'; }}>Plan</button></td></tr>)}</tbody></table></div>
      </Panel>
    </div>
  );
}

const skillNames = ['CNC', 'Milling', 'Drilling', 'Grinding', 'Inspection'] as const;

export function WorkforcePage() {
  const { data: operators } = useAsyncData(api.operators, fallbackOperators);
  const [query, setQuery] = useState('');
  const [shift, setShift] = useState('ALL');
  const shown = useMemo(() => operators.filter((operator) => `${operator.id} ${operator.name}`.toLowerCase().includes(query.toLowerCase()) && (shift === 'ALL' || operator.shift === shift)), [operators, query, shift]);
  return (
    <div className="page-stack">
      <PageHeader kicker="SKILLS-BASED WORKFORCE PLANNING" title="Workforce & skill matrix" description="Machine capacity counts only when a qualified, available operator can staff the planned shift." actions={<button className="button button-primary" onClick={() => window.alert('Cross-training request created for OP-07 and OP-19.')}>Create training plan <ArrowRight /></button>} />
      <div className="kpi-grid kpi-grid-4 compact-kpis"><KpiCard label="Present today" value="38 / 40" detail="1 absent · 1 leave" icon={<UserCheck />} /><KpiCard label="Grinding qualified" value="3" detail="Only 2 available today" tone="danger" icon={<AlertTriangle />} /><KpiCard label="Overtime eligible" value="32" detail="Within weekly limits" icon={<UsersRound />} /><KpiCard label="Skill coverage" value="86%" detail="Planned operations covered" icon={<Check />} /></div>
      <Panel className="training-callout"><div className="training-icon"><GraduationCap /></div><div><span className="eyebrow">HIGH-VALUE TRAINING RECOMMENDATION</span><h2>Cross-train OP-07 and OP-19 for grinding</h2><p>₹45,000 training cost removes a single-point Shift 2 dependency and is estimated to reduce annual penalty exposure by ₹2.4L. Simple payback: 2.3 months.</p></div><button className="button button-secondary" onClick={(event) => { event.currentTarget.textContent = 'Included in plan'; }}>Add to workforce plan</button></Panel>
      <Panel className="flush-panel">
        <div className="table-toolbar"><div className="table-title"><h2>Qualification matrix</h2><Badge tone="neutral">Level 1–3</Badge></div><div className="filter-row"><label className="search-field"><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find operator" /></label><label className="select-field"><select value={shift} onChange={(event) => setShift(event.target.value)}><option value="ALL">All shifts</option><option>Shift 1</option><option>Shift 2</option></select></label></div></div>
        <div className="table-scroll"><table className="skill-table"><thead><tr><th>Operator</th><th>Shift</th>{skillNames.map((skill) => <th key={skill}>{skill}</th>)}<th>Experience</th><th>Availability</th></tr></thead><tbody>{shown.map((operator) => <SkillRow key={operator.id} operator={operator} />)}</tbody></table></div>
        <div className="skill-legend"><span><i className="skill-dot level-0" />Not qualified</span><span><i className="skill-dot level-1" />Level 1 · Assisted</span><span><i className="skill-dot level-2" />Level 2 · Independent</span><span><i className="skill-dot level-3" />Level 3 · Trainer</span></div>
      </Panel>
    </div>
  );
}

function SkillRow({ operator }: { operator: Operator }) {
  return <tr><td><strong>{operator.id}</strong><small>{operator.name}</small></td><td>{operator.shift}<small>{operator.overtimeEligible ? 'OT eligible' : 'No OT'}</small></td>{skillNames.map((skill) => <td key={skill}><span className={`skill-level level-${operator.skills[skill]}`} title={`${skill} level ${operator.skills[skill]}`}>{operator.skills[skill] || '—'}</span></td>)}<td>{operator.experience} years</td><td><Badge tone={operator.status} dot>{operator.status}</Badge></td></tr>;
}
