import { useState } from 'react';
import { ArrowRight, Check, Factory, GraduationCap, Hammer, LoaderCircle, PackagePlus, Play, ShieldCheck, Sun, Truck, UserMinus, Wrench, Zap } from 'lucide-react';
import { api } from '../services/api';
import type { ScenarioResult } from '../types';
import { Badge, money, PageHeader, Panel, Progress } from '../components/UI';

const scenarios = [
  { id: 'grinder-breakdown', label: 'Grinding machine fails', icon: Wrench, unit: 'hours', defaultValue: 8, help: 'Remove GRIND-01 capacity' },
  { id: 'operator-absence', label: 'Operators absent', icon: UserMinus, unit: 'operators', defaultValue: 2, help: 'Recheck qualified coverage' },
  { id: 'power-failure', label: 'Power fails', icon: Zap, unit: 'hours', defaultValue: 8, help: 'Compare generator vs delay' },
  { id: 'quantity-increase', label: 'Order quantity grows', icon: PackagePlus, unit: '× 10%', defaultValue: 3, help: 'Increase ORD-018 demand' },
  { id: 'sunday-overtime', label: 'Run Sunday overtime', icon: Sun, unit: 'hours', defaultValue: 8, help: 'Add premium capacity' },
  { id: 'new-grinder', label: 'Add grinding machine', icon: Factory, unit: 'machine', defaultValue: 1, help: 'Test investment capacity' },
  { id: 'cross-train', label: 'Cross-train operators', icon: GraduationCap, unit: 'operators', defaultValue: 2, help: 'Reduce skill dependency' },
  { id: 'outsource', label: 'Outsource grinding', icon: Truck, unit: 'hours', defaultValue: 12, help: 'Buy external capacity' },
];

const baseline = { label: 'Approved robust plan', delivery: 95, revenue: 8_640_000, cost: 5_810_000, profit: 2_180_000, penalties: 164_000, overtime: 128_000, utilization: 78.4, bottleneckLoad: 96.2 };

export function ScenariosPage() {
  const [scenarioId, setScenarioId] = useState('grinder-breakdown');
  const selected = scenarios.find((item) => item.id === scenarioId)!;
  const [magnitude, setMagnitude] = useState(selected.defaultValue);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  async function run() { setLoading(true); setError(''); try { setResult(await api.runScenario(scenarioId, magnitude)); } catch (reason) { setError(reason instanceof Error ? reason.message : 'The scenario could not be calculated.'); } finally { setLoading(false); } }
  function choose(id: string) { const item = scenarios.find((scenario) => scenario.id === id)!; setScenarioId(id); setMagnitude(item.defaultValue); setResult(null); setError(''); }
  return (
    <div className="page-stack scenario-page">
      <PageHeader kicker="WHAT-IF SIMULATOR" title="Test a decision before changing the factory" description="Recalculate delivery, cost, profit and bottleneck load against the approved robust baseline." actions={<Badge tone="neutral">DETERMINISTIC · SEED 42</Badge>} />
      <div className="scenario-layout">
        <Panel className="scenario-input" title="Choose an intervention" eyebrow="SCENARIO DESIGN">
          <div className="scenario-grid">{scenarios.map((scenario) => <button key={scenario.id} className={scenarioId === scenario.id ? 'selected' : ''} onClick={() => choose(scenario.id)}><scenario.icon /><span><strong>{scenario.label}</strong><small>{scenario.help}</small></span>{scenarioId === scenario.id && <Check />}</button>)}</div>
          <div className="magnitude-control"><div><label htmlFor="magnitude">Magnitude</label><span><strong>{magnitude}</strong> {selected.unit}</span></div><input id="magnitude" type="range" min="1" max={scenarioId === 'new-grinder' ? 2 : 16} value={magnitude} onChange={(event) => { setMagnitude(Number(event.target.value)); setResult(null); }} /><div className="range-labels"><span>1</span><span>{scenarioId === 'new-grinder' ? '2' : '16'}</span></div></div>
          <div className="simulation-method"><ShieldCheck /><span><strong>What the simulation changes</strong><small>Resource calendars, dependent operations, recovery premiums, delivery penalties and contribution margin.</small></span></div>
          {error && <div className="form-error"><Wrench />{error}</div>}
          <button className="button button-primary button-large full-button" onClick={run} disabled={loading}>{loading ? <><LoaderCircle className="spin" />Running schedule simulation…</> : <><Play />Run scenario</>}</button>
        </Panel>
        <div className="scenario-output">
          {!result ? <Panel className="scenario-placeholder"><span className="placeholder-icon"><Hammer /></span><h2>Baseline ready</h2><p>Choose an intervention and run it against 25 open orders, 14 machines and the current shift roster.</p><div className="baseline-preview"><span><small>On-time delivery</small><strong>95%</strong></span><span><small>Expected profit</small><strong>₹21.8L</strong></span><span><small>Constraint load</small><strong>96.2%</strong></span></div></Panel> : <ScenarioOutput result={result} />}
        </div>
      </div>
      <Panel className="investment-panel" title="Investment decision support" eyebrow="APPROXIMATE ANNUALIZED CASE">
        <div className="investment-grid"><Investment title="Cross-train 2 grinder operators" icon={<GraduationCap />} cost={45_000} benefit={240_000} capacity="+16 operator h / week" payback="2.3 months" recommended /><Investment title="Additional grinding machine" icon={<Factory />} cost={2_800_000} benefit={3_140_000} capacity="+80 machine h / week" payback="10.7 months" /><Investment title="Grinding outsource contract" icon={<Truck />} cost={360_000} benefit={690_000} capacity="12 h protected / week" payback="6.3 months" /></div>
      </Panel>
    </div>
  );
}

function ScenarioOutput({ result }: { result: ScenarioResult }) {
  const comparisonBaseline = { ...baseline, ...(result.baseline ?? {}) };
  const valid = result.valid !== false;
  const fields: Array<{ label: string; key: keyof typeof baseline; format: (v: number) => string; higherBetter: boolean }> = [
    { label: 'On-time delivery', key: 'delivery', format: (v) => `${v.toFixed(1)}%`, higherBetter: true },
    { label: 'Revenue', key: 'revenue', format: (v) => money(v), higherBetter: true },
    { label: 'Operating cost', key: 'cost', format: (v) => money(v), higherBetter: false },
    { label: 'Expected profit', key: 'profit', format: (v) => money(v), higherBetter: true },
    { label: 'Late penalties', key: 'penalties', format: (v) => money(v), higherBetter: false },
    { label: 'Overtime cost', key: 'overtime', format: (v) => money(v), higherBetter: false },
    { label: 'Machine utilization', key: 'utilization', format: (v) => `${v.toFixed(1)}%`, higherBetter: true },
    { label: 'Bottleneck load', key: 'bottleneckLoad', format: (v) => `${v.toFixed(1)}%`, higherBetter: false },
  ];
  return <div className="result-stack"><Panel className="scenario-result-head"><div><span className="eyebrow">SIMULATION COMPLETE</span><h2>{result.label}</h2><p>Compared with the approved robust plan.</p></div><Badge tone={valid ? 'healthy' : 'critical'}>{valid ? <Check /> : <Wrench />}{valid ? 'VALID SCHEDULE' : 'CAPACITY INFEASIBLE'}</Badge></Panel><Panel className="scenario-comparison flush-panel"><div className="comparison-head"><span>Metric</span><span>Baseline</span><span>Scenario</span><span>Change</span></div>{fields.map((field) => { const before = Number(comparisonBaseline[field.key]); const after = Number(result[field.key]); const delta = after - before; const good = field.higherBetter ? delta >= 0 : delta <= 0; const monetary = field.key === 'revenue' || field.key === 'cost' || field.key === 'profit' || field.key === 'penalties' || field.key === 'overtime'; return <div className="comparison-row" key={field.label}><strong>{field.label}</strong><span>{field.format(before)}</span><span>{field.format(after)}</span><Badge tone={Math.abs(delta) < 0.01 ? 'neutral' : good ? 'healthy' : 'critical'}>{delta > 0 ? '+' : ''}{monetary ? money(delta) : `${delta.toFixed(1)} pts`}</Badge></div>; })}</Panel><Panel title="Management recommendation" eyebrow="EXPECTED-VALUE INTERPRETATION"><p className="scenario-recommendation">{result.recommendation}</p>{!valid && result.violations?.length ? <p className="explain-box"><Wrench />{result.violations[0].message}</p> : null}<div className="scenario-load"><span>Projected bottleneck load</span><Progress value={result.bottleneckLoad} label="GRIND-01" /></div></Panel></div>;
}

function Investment({ title, icon, cost, benefit, capacity, payback, recommended }: { title: string; icon: React.ReactNode; cost: number; benefit: number; capacity: string; payback: string; recommended?: boolean }) {
  return <div className={`investment-card ${recommended ? 'recommended' : ''}`}><div className="investment-title"><span>{icon}</span><div><h3>{title}</h3>{recommended && <Badge tone="healthy">QUICK WIN</Badge>}</div></div><div className="investment-numbers"><span><small>Investment</small><strong>{money(cost)}</strong></span><span><small>Annual benefit</small><strong>{money(benefit)}</strong></span></div><div className="resource-list compact"><div className="metric-row"><span>Capacity gained</span><strong>{capacity}</strong></div><div className="metric-row"><span>Simple payback</span><strong>{payback}</strong></div></div></div>;
}
