import { Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, BadgeIndianRupee, Bolt, Bot, CheckCircle2, CircleGauge, Clock3, Factory,
  Gauge, HardHat, PackageCheck, ShieldCheck, Siren, TrendingUp, Wrench,
} from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { costBreakdown, dashboard as fallbackDashboard, machines, orders, risks, throughputTrend } from '../data/demo';
import { useAsyncData } from '../hooks';
import { api } from '../services/api';
import { Badge, KpiCard, LinkArrow, MetricRow, money, PageHeader, Panel, Progress, SeverityBadge } from '../components/UI';

const tooltipStyle = { background: '#172733', border: '1px solid #2d4657', borderRadius: 8, color: '#fff', fontSize: 12 };

export function ExecutiveDashboard() {
  const { data } = useAsyncData(api.dashboard, fallbackDashboard);
  const riskyOrders = orders.filter((order) => order.status === 'AT_RISK' || order.status === 'DELAYED').slice(0, 4);
  return (
    <div className="page-stack">
      <PageHeader
        kicker="EXECUTIVE OVERVIEW · TUESDAY, 01 SEPTEMBER"
        title="Factory performance"
        description="Commercial and operating performance for the current two-week planning horizon."
        actions={<><button className="button button-secondary" onClick={() => window.print()}>Export brief</button><Link className="button button-primary" to="/plan-comparison">Compare plans <ArrowRight /></Link></>}
      />
      <div className="kpi-grid kpi-grid-5">
        <KpiCard label="Expected profit" value={money(data.expectedProfit)} trend={6.8} trendLabel="vs previous horizon" tone="profit" icon={<BadgeIndianRupee />} />
        <KpiCard label="On-time delivery" value={`${data.onTimeDelivery}%`} trend={2.4} trendLabel="target 95%" icon={<PackageCheck />} />
        <KpiCard label="Machine utilization" value={`${data.machineUtilization}%`} trend={1.6} trendLabel="14 machines" icon={<Gauge />} />
        <KpiCard label="Simplified OEE" value={`${data.oee}%`} trend={-1.2} trendLabel="availability × performance × quality" icon={<CircleGauge />} />
        <KpiCard label="Penalty exposure" value={money(data.latePenalties)} trend={-12.5} trendLabel="3 orders at risk" tone="danger" icon={<AlertTriangle />} />
      </div>

      <div className="dashboard-grid executive-grid">
        <Panel className="span-8" title="Output vs plan" eyebrow="LAST 7 PRODUCTION DAYS" action={<Badge tone="healthy" dot>96.1% plan attained</Badge>}>
          <div className="chart-lg" role="img" aria-label="Daily planned and actual production output">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={throughputTrend} margin={{ top: 12, right: 12, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d08a2e" stopOpacity={0.28} /><stop offset="100%" stopColor="#d08a2e" stopOpacity={0.02} /></linearGradient>
                </defs>
                <CartesianGrid stroke="#e7ecef" strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#6b7c87', fontSize: 11 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6b7c87', fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: '#d7dee2' }} />
                <Area type="monotone" dataKey="planned" stroke="#8aa0ad" strokeDasharray="5 4" fill="none" strokeWidth={2} />
                <Area type="monotone" dataKey="actual" stroke="#c27b22" fill="url(#actualFill)" strokeWidth={2.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-legend"><span><i style={{ background: '#c27b22' }} />Actual output</span><span><i className="legend-line" />Plan</span><span className="muted">Units completed at inspection</span></div>
        </Panel>
        <Panel className="span-4" title="Cost structure" eyebrow="CURRENT HORIZON" action={<strong>{money(data.productionCost)}</strong>}>
          <div className="donut-wrap">
            <div className="chart-donut" role="img" aria-label="Production cost breakdown">
              <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={costBreakdown} dataKey="value" nameKey="name" innerRadius={54} outerRadius={76} paddingAngle={2}>{costBreakdown.map((entry) => <Cell key={entry.name} fill={entry.color} />)}</Pie><Tooltip contentStyle={tooltipStyle} formatter={(value) => money(Number(value))} /></PieChart></ResponsiveContainer>
              <div className="donut-center"><strong>₹58.1L</strong><span>Total cost</span></div>
            </div>
            <div className="legend-list">{costBreakdown.map((item) => <div key={item.name}><span><i style={{ background: item.color }} />{item.name}</span><strong>{Math.round(item.value / data.productionCost * 100)}%</strong></div>)}</div>
          </div>
        </Panel>
      </div>

      <div className="dashboard-grid">
        <Panel className="span-7 flush-panel" title="Orders requiring attention" eyebrow="DELIVERY CONTROL" action={<Link className="text-link" to="/orders">All orders <ArrowRight /></Link>}>
          <div className="table-scroll"><table><thead><tr><th>Order</th><th>Customer</th><th>Due</th><th>Confidence</th><th>Exposure</th><th>Status</th></tr></thead><tbody>{riskyOrders.map((order) => <tr key={order.id}><td><Link to={`/orders/${order.id}`} className="table-primary">{order.id}</Link><small>{order.part} · {order.quantity.toLocaleString('en-IN')} pcs</small></td><td>{order.customer}<small>{order.tier}</small></td><td>{new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' }).format(new Date(`${order.dueDate}T12:00:00`))}</td><td><div className="confidence-cell"><Progress value={order.deliveryProbability} tone={order.deliveryProbability < 70 ? 'critical' : 'warning'} /><strong>{order.deliveryProbability}%</strong></div></td><td>{money(order.expectedPenalty)}</td><td><Badge tone={order.status}>{order.status.replace('_', ' ')}</Badge></td></tr>)}</tbody></table></div>
        </Panel>
        <Panel className="span-5" title="Resource pulse" eyebrow="FACTORY STATUS">
          <div className="status-tiles">
            <div><span className="status-icon running"><Factory /></span><strong>7</strong><small>Running</small></div>
            <div><span className="status-icon idle"><Clock3 /></span><strong>4</strong><small>Idle / setup</small></div>
            <div><span className="status-icon warning"><Wrench /></span><strong>1</strong><small>Maintenance</small></div>
            <div><span className="status-icon healthy"><HardHat /></span><strong>38/40</strong><small>Operators</small></div>
          </div>
          <div className="resource-list">
            <MetricRow label="GRIND-01 bottleneck load" value="96.2%" tone="critical" />
            <MetricRow label="Grid power" value={<Badge tone="healthy" dot>STABLE</Badge>} />
            <MetricRow label="Generator" value="Ready · 250 kVA" />
            <MetricRow label="Material shortages" value={<Badge tone="high">1 BLOCKED</Badge>} />
            <MetricRow label="Labour utilization" value={`${data.labourUtilization}%`} />
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function ControlTower() {
  const currentRisks = risks.filter((risk) => !risk.future).slice(0, 3);
  return (
    <div className="page-stack control-tower">
      <PageHeader
        kicker="FACTORY CONTROL TOWER · LIVE OPERATING PICTURE"
        title="Good morning, Raj. The plan needs 3 decisions."
        description="Production is 96% to plan. Grinding capacity and one Tier-1 dispatch need management attention before 10:00."
        actions={<Link to="/schedule" className="button button-secondary"><CalendarIcon />Two-week schedule</Link>}
      />
      <div className="health-ribbon">
        <div><span className="ribbon-icon good"><CheckCircle2 /></span><span><small>Schedule health</small><strong>Mostly on track</strong></span><Badge tone="healthy">22 / 25 protected</Badge></div>
        <div><span className="ribbon-icon critical"><Siren /></span><span><small>At-risk value</small><strong>₹18.6L</strong></span><span className="ribbon-detail">3 orders</span></div>
        <div><span className="ribbon-icon warning"><Gauge /></span><span><small>Constraint</small><strong>GRIND-01</strong></span><span className="ribbon-detail">96.2% loaded</span></div>
        <div><span className="ribbon-icon good"><Bolt /></span><span><small>Power</small><strong>Grid stable</strong></span><span className="ribbon-detail">Outage Thu 14:00</span></div>
        <div><span className="ribbon-icon good"><TrendingUp /></span><span><small>Expected profit</small><strong>₹21.8L</strong></span><span className="ribbon-detail">+6.8%</span></div>
      </div>

      <div className="tower-grid">
        <Panel className="tower-actions" title="Action required" eyebrow="MANAGEMENT QUEUE" action={<Badge tone="critical">3 DUE</Badge>}>
          <div className="action-list">
            {currentRisks.map((risk, index) => (
              <Link to="/risks" className="action-card" key={risk.id}>
                <span className={`action-number severity-${risk.severity.toLowerCase()}`}>{String(index + 1).padStart(2, '0')}</span>
                <div className="action-body">
                  <div className="action-meta"><SeverityBadge level={risk.severity} /><span>{risk.category}</span><span>{risk.detected}</span></div>
                  <h3>{risk.title}</h3>
                  <p>{risk.recommendation}</p>
                  <div className="decision-line"><strong>Why:</strong> {risk.rationale}</div>
                </div>
                <div className="action-impact"><small>Financial exposure</small><strong>{money(risk.financialImpact)}</strong><LinkArrow /></div>
              </Link>
            ))}
          </div>
          <div className="panel-cta"><Link to="/risks" className="button button-primary">Open risk control center <ArrowRight /></Link><span>4 more items are being monitored</span></div>
        </Panel>

        <div className="tower-side">
          <Panel className="bottleneck-card" title="GRIND-01" eyebrow="TODAY'S BOTTLENECK" action={<Badge tone="critical" dot>CRITICAL</Badge>}>
            <div className="bottleneck-gauge"><div><strong>96.2%</strong><span>committed</span></div></div>
            <Progress value={96.2} label="Load" />
            <div className="three-metrics"><div><span>Queue</span><strong>42 h</strong></div><div><span>Orders</span><strong>8</strong></div><div><span>Revenue</span><strong>₹34.8L</strong></div></div>
            <p className="explain-box"><ShieldCheck />Protect 12 hours reserve next week. Moving ORD-021 earlier and outsourcing 5.5 hours reduces projected load to 88%.</p>
            <Link className="text-link" to="/capacity">View capacity detail <ArrowRight /></Link>
          </Panel>
          <Panel title="Owner's next call" eyebrow="DISRUPTION READINESS" className="owner-call">
            <div className="owner-contact"><span>RG</span><div><strong>Ravi Grinding Services</strong><small>Approved outsourcing vendor · Hosur</small></div></div>
            <p>Reserve a 5.5-hour slot for ORD-014. This frees critical capacity and protects the Apex Driveline shipment worth ₹9.4L.</p>
            <div className="call-economics"><MetricRow label="Outsource cost" value="₹34,000" /><MetricRow label="Penalty protected" value="₹1,65,000" tone="healthy" /></div>
            <button className="button button-secondary full-button" onClick={(event) => { event.currentTarget.textContent = 'Call brief copied'; navigator.clipboard?.writeText('Call Ravi Grinding Services: reserve 5.5 hours for ORD-014.'); }}>Copy call brief</button>
          </Panel>
        </div>
      </div>

      <div className="dashboard-grid">
        <Panel className="span-8" title="Fourteen-day load profile" eyebrow="FINITE CAPACITY" action={<Link to="/schedule" className="text-link">Open schedule <ArrowRight /></Link>}>
          <div className="chart-md"><ResponsiveContainer width="100%" height="100%"><BarChart data={machines.slice(0, 9)} layout="vertical" margin={{ left: 4, right: 26 }}><CartesianGrid stroke="#e7ecef" strokeDasharray="3 4" horizontal={false} /><XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 11 }} /><YAxis type="category" dataKey="id" width={66} axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#425563' }} /><Tooltip contentStyle={tooltipStyle} formatter={(value) => `${value}%`} /><Bar dataKey="utilization" radius={[0, 4, 4, 0]}>{machines.slice(0, 9).map((machine) => <Cell key={machine.id} fill={machine.utilization >= 90 ? '#ad554c' : machine.utilization >= 82 ? '#d08a2e' : '#52748b'} />)}</Bar></BarChart></ResponsiveContainer></div>
        </Panel>
        <Panel className="span-4" title="Incoming RFQ" eyebrow="CAPABLE-TO-PROMISE" action={<Badge tone="healthy">GOOD FIT</Badge>}>
          <div className="rfq-peek"><div className="rfq-title"><span>RFQ-006</span><strong>AX-206 · 1,200 pcs</strong><small>Apex Driveline · Tier 1</small></div><div className="rfq-score"><strong>82</strong><span>attractiveness</span></div></div>
          <div className="resource-list"><MetricRow label="Projected revenue" value="₹8.4L" /><MetricRow label="Expected margin" value="₹2.04L" tone="healthy" /><MetricRow label="Delivery confidence" value="94%" /><MetricRow label="GRIND-01 after insert" value="98.7%" tone="warning" /></div>
          <p className="explain-box"><Bot />Recommendation uses finite capacity and risk-adjusted cost logic. It is not a generated text guess.</p>
          <Link className="button button-primary full-button" to="/acceptance">Evaluate order <ArrowRight /></Link>
        </Panel>
      </div>
    </div>
  );
}

function CalendarIcon() { return <Clock3 />; }
