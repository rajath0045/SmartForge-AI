import { FormEvent, useEffect, useMemo, useState } from 'react';
import { AlertOctagon, ArrowRight, Bolt, Check, CircleAlert, Clock3, Factory, LoaderCircle, PackageX, Phone, RefreshCw, ShieldAlert, Siren, TriangleAlert, UserMinus, Wrench } from 'lucide-react';
import { CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { risks as fallbackRisks } from '../data/demo';
import { useAsyncData } from '../hooks';
import { api } from '../services/api';
import type { DisruptionInput, ReplanResult, RiskItem, RiskLevel } from '../types';
import { Badge, KpiCard, MetricRow, money, PageHeader, Panel, SeverityBadge } from '../components/UI';
import { ChartTooltip, InteractiveChartCard } from '../components/Analytics';

const categoryIcons = { DELIVERY: PackageX, MACHINE: Wrench, LABOUR: UserMinus, MATERIAL: Factory, POWER: Bolt, QUALITY: CircleAlert, CAPACITY: ShieldAlert };

export function RisksPage() {
  const { data: remoteRisks } = useAsyncData(api.risks, fallbackRisks);
  const [items, setItems] = useState<RiskItem[]>(remoteRisks);
  const [severity, setSeverity] = useState<'ALL' | RiskLevel>('ALL');
  const [tab, setTab] = useState<'current' | 'future'>('current');
  const [expanded, setExpanded] = useState<string | null>('RSK-101');
  useEffect(() => { setItems(remoteRisks); }, [remoteRisks]);
  const shown = useMemo(() => items.filter((risk) => Boolean(risk.future) === (tab === 'future') && (severity === 'ALL' || risk.severity === severity)), [items, tab, severity]);
  const riskMatrix = useMemo(() => items.map((risk) => ({ name: risk.title, probability: risk.probability, impact: risk.financialImpact / 100_000, exposure: risk.probability * risk.financialImpact / 100, severity: risk.severity })), [items]);
  function acknowledge(id: string) { setItems((current) => current.map((risk) => risk.id === id ? { ...risk, status: 'MITIGATED' } : risk)); }
  return (
    <div className="page-stack risks-page">
      <PageHeader kicker="PROBLEMS & RISK CONTROL CENTER" title="See the problem before it becomes a penalty" description="Current exceptions, forward risk signals and financially justified management actions in one queue." actions={<button className="button button-secondary" onClick={() => window.print()}>Export action log</button>} />
      <div className="kpi-grid kpi-grid-4 compact-kpis"><KpiCard label="Critical now" value={String(items.filter((risk) => !risk.future && risk.severity === 'CRITICAL').length)} detail="Immediate decision" tone="danger" icon={<Siren />} /><KpiCard label="Open exposure" value={money(items.filter((risk) => risk.status !== 'MITIGATED').reduce((sum, risk) => sum + risk.financialImpact, 0))} detail="Expected-value estimate" icon={<AlertOctagon />} /><KpiCard label="Future signals" value={String(items.filter((risk) => risk.future).length)} detail="Next 14 days" icon={<Clock3 />} /><KpiCard label="Awaiting approval" value={String(items.filter((risk) => risk.status === 'APPROVAL_REQUIRED').length)} detail="₹1.85L avoidable loss" icon={<ShieldAlert />} /></div>
      <InteractiveChartCard title="Risk exposure matrix" eyebrow="PROBABILITY × FINANCIAL IMPACT" className="risk-matrix-panel" insight="Items in the upper-right require management action first; bubble size represents probability-weighted expected loss." details={<div className="chart-detail-grid"><span><small>Highest exposure</small><strong>{[...items].sort((a, b) => b.financialImpact * b.probability - a.financialImpact * a.probability)[0]?.title}</strong></span><span><small>Open risks</small><strong>{items.filter((risk) => risk.status !== 'MITIGATED').length}</strong></span><span><small>14-day horizon</small><strong>{money(items.reduce((sum, risk) => sum + risk.financialImpact * risk.probability / 100, 0))} expected loss</strong></span></div>}>
        <div className="risk-matrix-chart"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 10, right: 24, bottom: 8, left: 8 }}><CartesianGrid strokeDasharray="3 5" /><XAxis type="number" dataKey="probability" name="Probability" unit="%" domain={[0, 100]} tickLine={false} axisLine={false} /><YAxis type="number" dataKey="impact" name="Impact" unit="L" tickLine={false} axisLine={false} /><ZAxis type="number" dataKey="exposure" range={[90, 420]} /><Tooltip content={<ChartTooltip formatter={(value, name) => name === 'Impact' ? `₹${value.toFixed(1)}L` : `${value.toFixed(0)}%`} />} /><Scatter data={riskMatrix}>{riskMatrix.map((risk) => <Cell key={risk.name} fill={risk.severity === 'CRITICAL' ? '#c77870' : risk.severity === 'HIGH' ? '#b88770' : risk.severity === 'MEDIUM' ? '#c9aa73' : '#89aa91'} />)}</Scatter></ScatterChart></ResponsiveContainer><span className="matrix-label matrix-low">MONITOR</span><span className="matrix-label matrix-high">ACT NOW</span></div>
      </InteractiveChartCard>
      <div className="risk-toolbar"><div className="tab-list"><button className={tab === 'current' ? 'active' : ''} onClick={() => setTab('current')}>Current problems <Badge tone="critical">{items.filter((risk) => !risk.future).length}</Badge></button><button className={tab === 'future' ? 'active' : ''} onClick={() => setTab('future')}>Expected future problems <Badge tone="warning">{items.filter((risk) => risk.future).length}</Badge></button></div><label className="select-field"><select value={severity} onChange={(event) => setSeverity(event.target.value as 'ALL' | RiskLevel)}><option value="ALL">All severity</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></label></div>
      <div className="risk-list">{shown.map((risk) => {
        const Icon = categoryIcons[risk.category];
        const isOpen = expanded === risk.id;
        return <article key={risk.id} className={`risk-card risk-${risk.severity.toLowerCase()} ${isOpen ? 'expanded' : ''}`}><button className="risk-summary" onClick={() => setExpanded(isOpen ? null : risk.id)} aria-expanded={isOpen}><span className={`risk-category category-${risk.category.toLowerCase()}`}><Icon /></span><div className="risk-main"><div className="risk-meta"><SeverityBadge level={risk.severity} /><Badge tone="neutral">{risk.category}</Badge><span>{risk.detected}</span></div><h2>{risk.title}</h2><p>{risk.deliveryImpact} · {risk.affected.join(' · ')}</p></div><div className="risk-probability"><span>{risk.future ? 'Probability' : 'Financial impact'}</span><strong>{risk.future ? `${risk.probability}%` : money(risk.financialImpact)}</strong></div><Badge tone={risk.status}>{risk.status.replace('_', ' ')}</Badge><ArrowRight className="risk-chevron" /></button>{isOpen && <div className="risk-detail"><div className="recommended-action"><span className="recommend-icon"><ShieldAlert /></span><div><small>RECOMMENDED ACTION</small><h3>{risk.recommendation}</h3><p><strong>Financial justification:</strong> {risk.rationale}</p></div></div><div className="risk-detail-metrics"><MetricRow label="Expected loss" value={money(risk.financialImpact, false)} /><MetricRow label="Delivery impact" value={risk.deliveryImpact} /><MetricRow label="Orders / resources" value={risk.affected.join(', ')} /><MetricRow label="Likelihood" value={`${risk.probability}%`} /></div><div className="risk-actions"><button className="button button-secondary" onClick={() => setExpanded(null)}>Keep monitoring</button><button className="button button-primary" disabled={risk.status === 'MITIGATED'} onClick={() => acknowledge(risk.id)}>{risk.status === 'MITIGATED' ? <><Check />Action recorded</> : 'Approve recommended action'}</button></div></div>}</article>;
      })}</div>
    </div>
  );
}

const disruptionKinds: Array<{ type: DisruptionInput['type']; label: string; icon: typeof Wrench; helper: string }> = [
  { type: 'MACHINE_BREAKDOWN', label: 'Machine breakdown', icon: Wrench, helper: 'Remove capacity during repair' },
  { type: 'OPERATOR_ABSENCE', label: 'Operator absence', icon: UserMinus, helper: 'Recheck skill coverage' },
  { type: 'MATERIAL_DELAY', label: 'Material delay', icon: Factory, helper: 'Hold blocked operations' },
  { type: 'QUALITY_REWORK', label: 'Quality / rework', icon: CircleAlert, helper: 'Insert rework routing' },
  { type: 'POWER_CUT', label: 'Power cut', icon: Bolt, helper: 'Compare DG economics' },
];

export function DisruptionsPage() {
  const [input, setInput] = useState<DisruptionInput>({ type: 'MACHINE_BREAKDOWN', resource: 'GRIND-01', start: '2026-09-02T11:00', durationHours: 8, notes: 'Grinding operator OP-15 is also absent.' });
  const [result, setResult] = useState<ReplanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  async function run(event: FormEvent) { event.preventDefault(); setLoading(true); setError(''); try { setResult(await api.injectDisruption(input)); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Replanning could not be completed.'); } finally { setLoading(false); } }
  function selectType(type: DisruptionInput['type']) {
    const resources: Record<DisruptionInput['type'], string> = { MACHINE_BREAKDOWN: 'GRIND-01', OPERATOR_ABSENCE: 'OP-15', MATERIAL_DELAY: 'ORD-014 · EN8 Round Bar', QUALITY_REWORK: 'ORD-018 · 5% rejected', POWER_CUT: 'Plant 01 grid supply' };
    setInput((current) => ({ ...current, type, resource: resources[type] })); setResult(null); setError('');
  }
  return (
    <div className="page-stack disruption-page">
      <PageHeader kicker="DYNAMIC RESCHEDULING" title="Disruption control center" description="Freeze completed work, preserve realistic work in progress, recalculate remaining capacity and compare the revised schedule against baseline." actions={<Badge tone="healthy"><Check />BASELINE VALID</Badge>} />
      <div className="disruption-layout">
        <Panel className="disruption-input" title="Inject factory event" eyebrow="DEMONSTRATION SCENARIO">
          <form onSubmit={run} className="form-stack">
            <div className="disruption-types">{disruptionKinds.map((kind) => <button type="button" key={kind.type} className={input.type === kind.type ? 'selected' : ''} onClick={() => selectType(kind.type)}><kind.icon /><span><strong>{kind.label}</strong><small>{kind.helper}</small></span>{input.type === kind.type && <Check />}</button>)}</div>
            <div className="form-grid"><label><span>Affected resource / order</span><input required value={input.resource} onChange={(event) => setInput({ ...input, resource: event.target.value })} /></label><div className="two-col"><label><span>Event start</span><input required type="datetime-local" value={input.start} onChange={(event) => setInput({ ...input, start: event.target.value })} /></label><label><span>Duration (hours)</span><input required type="number" min="1" max="168" value={input.durationHours} onChange={(event) => setInput({ ...input, durationHours: Number(event.target.value) })} /></label></div><label><span>Additional context</span><textarea value={input.notes} onChange={(event) => setInput({ ...input, notes: event.target.value })} rows={3} /></label></div>
            <div className="freeze-note"><Check /><span><strong>Safe replanning rules</strong>Completed operations remain frozen. Active work is preserved where the resource remains usable.</span></div>
            {error && <div className="form-error"><TriangleAlert />{error}</div>}
            <button className="button button-danger button-large full-button" disabled={loading}>{loading ? <><LoaderCircle className="spin" />Replanning remaining work…</> : <><RefreshCw />Inject event & replan</>}</button>
          </form>
        </Panel>
        <div className="disruption-result">{result ? <ReplanOutput result={result} /> : <Panel className="replan-placeholder"><span className="placeholder-icon"><RefreshCw /></span><h2>Baseline schedule is protected</h2><p>Select an event and run replanning to see every operation, cost and promise-date change.</p><div className="method-list"><span><Check />Freeze completed operations</span><span><Check />Recalculate machine and labour capacity</span><span><Check />Minimize movement and incremental cost</span><span><Check />Validate the revised schedule</span></div></Panel>}</div>
      </div>
    </div>
  );
}

function ReplanOutput({ result }: { result: ReplanResult }) {
  const valid = result.valid !== false;
  return <div className="result-stack"><Panel className="replan-success"><div className="replan-status"><span>{valid ? <Check /> : <TriangleAlert />}</span><div><div className="eyebrow">{valid ? 'REVISED SCHEDULE VALID' : 'CAPACITY INFEASIBLE'}</div><h2>{valid ? 'Recovery plan generated' : 'Recovery plan requires escalation'}</h2><p>{result.explanation}</p>{!valid && result.violations?.length ? <p>{result.violations[0].message}</p> : null}</div></div><div className="replan-cost"><span>Total disruption cost</span><strong>{money(result.disruptionCost, false)}</strong></div></Panel><div className="replan-kpis"><div><span>Jobs moved</span><strong>{result.jobsMoved}</strong></div><div><span>New overtime</span><strong>{result.newOvertimeHours} h</strong></div><div><span>Penalty increase</span><strong>{money(result.penaltyIncrease)}</strong></div><div><span>Lost output</span><strong>{result.lostProduction} pcs</strong></div></div><Panel className="flush-panel" title="Schedule difference" eyebrow="BEFORE → AFTER"><div className="change-list">{result.changes.map((change) => <div key={`${change.order}-${change.operation}`}><span><strong>{change.order}</strong><small>{change.operation}</small></span><span className="change-before">{change.before}</span><ArrowRight /><span className="change-after">{change.after}</span><Badge tone={change.impact.includes('₹') ? 'warning' : 'neutral'}>{change.impact}</Badge></div>)}</div></Panel><Panel className="owner-call-result" title="Owner's next call" eyebrow="HUMAN COORDINATION"><div className="call-result"><span><Phone /></span><div><small>CALL</small><h3>{result.ownerCall.contact}</h3><p>{result.ownerCall.reason}</p></div></div><button className="button button-secondary full-button" onClick={(event) => { event.currentTarget.textContent = 'Call brief copied'; navigator.clipboard?.writeText(result.ownerCall.reason); }}>Copy call brief</button></Panel></div>;
}
