import { FormEvent, useState } from 'react';
import { ArrowRight, BadgeIndianRupee, CalendarCheck, Check, CircleHelp, Factory, LoaderCircle, RotateCcw, ShieldCheck, TriangleAlert, X } from 'lucide-react';
import { api } from '../services/api';
import type { RfqInput, RfqResult, Tier } from '../types';
import { Badge, MetricRow, money, PageHeader, Panel, Progress } from '../components/UI';

const operations = ['Turning', 'Milling', 'Drilling', 'Grinding', 'Inspection'];
const initialInput: RfqInput = {
  customer: 'Apex Driveline',
  tier: 'Tier 1',
  part: 'AX-206',
  quantity: 1200,
  requestedDate: '2026-09-04',
  sellingPrice: 840000,
  latePenalty: 76000,
  operations: ['Turning', 'Milling', 'Grinding', 'Inspection'],
  materialAvailable: true,
};

export function AcceptancePage() {
  const [input, setInput] = useState<RfqInput>(initialInput);
  const [result, setResult] = useState<RfqResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function update<K extends keyof RfqInput>(key: K, value: RfqInput[K]) { setInput((current) => ({ ...current, [key]: value })); }
  function toggleOperation(operation: string) {
    update('operations', input.operations.includes(operation) ? input.operations.filter((item) => item !== operation) : [...input.operations, operation]);
  }
  async function evaluate(event: FormEvent) {
    event.preventDefault();
    if (input.operations.length === 0) { setError('Select at least one required operation.'); return; }
    setLoading(true); setError('');
    try { setResult(await api.evaluateRfq(input)); }
    catch { setError('The feasibility calculation could not be completed. Please check the inputs and try again.'); }
    finally { setLoading(false); }
  }

  return (
    <div className="page-stack acceptance-page">
      <PageHeader kicker="CAPABLE-TO-PROMISE" title="Smart order acceptance" description="Insert a candidate order into current finite capacity, then compare its contribution against the risk it creates for existing commitments." actions={<button className="button button-secondary" onClick={() => { setInput(initialInput); setResult(null); }}><RotateCcw />Reset example</button>} />
      <div className="acceptance-layout">
        <Panel className="rfq-form-panel" eyebrow="NEW REQUEST FOR QUOTE" title="Commercial and routing inputs">
          <form onSubmit={evaluate} className="form-stack">
            <div className="form-grid two-col">
              <label><span>Customer</span><input required value={input.customer} onChange={(event) => update('customer', event.target.value)} /></label>
              <label><span>Customer tier</span><select value={input.tier} onChange={(event) => update('tier', event.target.value as Tier)}><option>Tier 1</option><option>Tier 2</option><option>Tier 3</option></select></label>
              <label><span>Part number</span><input required value={input.part} onChange={(event) => update('part', event.target.value.toUpperCase())} /></label>
              <label><span>Quantity (pieces)</span><input required min="1" max="50000" type="number" value={input.quantity} onChange={(event) => update('quantity', Number(event.target.value))} /></label>
              <label><span>Requested delivery</span><input required type="date" min="2026-09-02" value={input.requestedDate} onChange={(event) => update('requestedDate', event.target.value)} /></label>
              <label><span>Total selling price (₹)</span><input required min="1" type="number" value={input.sellingPrice} onChange={(event) => update('sellingPrice', Number(event.target.value))} /></label>
              <label><span>Late penalty / day (₹)</span><input required min="0" type="number" value={input.latePenalty} onChange={(event) => update('latePenalty', Number(event.target.value))} /></label>
              <label><span>Raw material</span><select value={input.materialAvailable ? 'available' : 'incoming'} onChange={(event) => update('materialAvailable', event.target.value === 'available')}><option value="available">Available in stock</option><option value="incoming">Incoming · 2-day lead</option></select></label>
            </div>
            <fieldset className="operation-picker"><legend>Required routing</legend><p>Select operations in the intended process route.</p><div>{operations.map((operation, index) => <button type="button" key={operation} className={input.operations.includes(operation) ? 'selected' : ''} onClick={() => toggleOperation(operation)}><span>{input.operations.includes(operation) ? <Check /> : index + 1}</span>{operation}</button>)}</div></fieldset>
            {error && <div className="form-error"><TriangleAlert />{error}</div>}
            <div className="form-footer"><span><ShieldCheck />Existing committed orders remain protected by penalty and priority constraints.</span><button className="button button-primary button-large" disabled={loading}>{loading ? <><LoaderCircle className="spin" />Evaluating capacity…</> : <>Evaluate order <ArrowRight /></>}</button></div>
          </form>
        </Panel>

        <div className="acceptance-result">
          {!result ? (
            <Panel className="result-placeholder">
              <div className="placeholder-icon"><Factory /></div><h2>Ready to evaluate</h2><p>The calculation checks machine hours, qualified labour, material timing, power economics and penalty risk across the current schedule.</p>
              <div className="method-list"><span><Check />Finite machine capacity</span><span><Check />Operator qualifications</span><span><Check />Existing Tier-1 exposure</span><span><Check />Expected contribution margin</span></div>
            </Panel>
          ) : <AcceptanceResult result={result} />}
        </div>
      </div>
    </div>
  );
}

function AcceptanceResult({ result }: { result: RfqResult }) {
  const reject = result.decision === 'REJECT';
  const caution = result.decision.includes('NEGOTIATED') || result.decision.includes('OUTSOURCE') || result.decision.includes('PARTIAL');
  const tone = reject ? 'critical' : caution ? 'warning' : 'healthy';
  return (
    <div className="result-stack">
      <Panel className={`decision-result decision-${tone}`}>
        <div className="decision-result-top"><span className="decision-symbol">{reject ? <X /> : caution ? <TriangleAlert /> : <Check />}</span><div><div className="eyebrow">RECOMMENDED DECISION</div><h2>{result.decision}</h2><p>Delivery confidence <strong>{result.confidence}%</strong> · attractiveness score <strong>{result.score}/100</strong></p></div></div>
        {result.recommendedDate !== result.requestedDate && <div className="promise-date"><CalendarCheck /><span><small>Requested date</small><strong>{result.requestedDate}</strong></span><ArrowRight /><span><small>Recommended promise</small><strong>{result.recommendedDate}</strong></span></div>}
        <div className="confidence-meter"><div><span>Delivery confidence</span><strong>{result.confidence}%</strong></div><Progress value={result.confidence} tone={tone} /></div>
      </Panel>
      <Panel title="Risk-adjusted economics" eyebrow="EXPECTED VALUE" action={<Badge tone={result.contributionMargin > 0 ? 'healthy' : 'critical'}>{result.contributionMargin > 0 ? 'POSITIVE' : 'NEGATIVE'}</Badge>}>
        <div className="economics-hero"><div><span>Expected contribution</span><strong>{money(result.contributionMargin, false)}</strong></div><BadgeIndianRupee /></div>
        <div className="resource-list"><MetricRow label="Revenue" value={money(result.revenue, false)} /><MetricRow label="Production cost" value={`− ${money(result.productionCost, false)}`} /><MetricRow label="Overtime" value={`− ${money(result.overtimeCost, false)}`} /><MetricRow label="Generator" value={`− ${money(result.generatorCost, false)}`} /><MetricRow label="Expected penalty" value={`− ${money(result.expectedPenalty, false)}`} tone={result.expectedPenalty > 0 ? 'critical' : undefined} /></div>
      </Panel>
      <Panel title="Capacity gates" eyebrow="INSERTION CHECK">
        <div className="capacity-check-list">{result.capacityChecks.map((check) => <div key={check.label}><span className={`check-state state-${check.state.toLowerCase()}`}>{check.state === 'LOW' ? <Check /> : <TriangleAlert />}</span><span><strong>{check.label}</strong><small>{check.value}</small></span><Badge tone={check.state}>{check.state === 'LOW' ? 'PASS' : check.state}</Badge></div>)}</div>
      </Panel>
      <Panel title="Why this recommendation" eyebrow="EXPLAINABLE RULES" action={<CircleHelp />}>
        <ol className="reason-list">{result.reasons.map((reason, index) => <li key={reason}><span>{index + 1}</span><p>{reason}</p></li>)}</ol>
      </Panel>
    </div>
  );
}
