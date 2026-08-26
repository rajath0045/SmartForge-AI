import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, CalendarClock, Download, Filter, PackageOpen, Search, ShieldCheck, Truck } from 'lucide-react';
import { orders as fallbackOrders } from '../data/demo';
import { useAsyncData } from '../hooks';
import { api } from '../services/api';
import type { Order } from '../types';
import { Badge, dateLabel, EmptyState, KpiCard, MetricRow, money, PageHeader, Panel, Progress, SeverityBadge } from '../components/UI';

export function OrdersPage() {
  const { data: orders } = useAsyncData(api.orders, fallbackOrders);
  const [query, setQuery] = useState('');
  const [tier, setTier] = useState('ALL');
  const [status, setStatus] = useState('ALL');
  const filtered = useMemo(() => orders.filter((order) => {
    const matchesQuery = `${order.id} ${order.customer} ${order.part}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (tier === 'ALL' || order.tier === tier) && (status === 'ALL' || order.status === status);
  }), [orders, query, tier, status]);
  const committedRevenue = orders.reduce((sum, order) => sum + order.revenue, 0);

  return (
    <div className="page-stack">
      <PageHeader kicker="CUSTOMER COMMITMENTS" title="Orders" description="Track every open order from material release through dispatch confidence and expected margin." actions={<><button className="button button-secondary" onClick={() => window.print()}><Download />Export</button><Link className="button button-primary" to="/acceptance">Evaluate new RFQ <ArrowRight /></Link></>} />
      <div className="kpi-grid kpi-grid-4 compact-kpis">
        <KpiCard label="Open orders" value={String(orders.length)} detail="Across 8 customers" icon={<PackageOpen />} />
        <KpiCard label="Committed revenue" value={money(committedRevenue)} detail="Current two-week horizon" icon={<Truck />} />
        <KpiCard label="At risk / delayed" value={String(orders.filter((order) => ['AT_RISK', 'DELAYED'].includes(order.status)).length)} detail="₹3.6L penalty exposure" tone="danger" icon={<CalendarClock />} />
        <KpiCard label="Weighted confidence" value="91.8%" detail="Risk-adjusted delivery" icon={<ShieldCheck />} />
      </div>
      <Panel className="flush-panel orders-panel">
        <div className="table-toolbar">
          <div className="table-title"><h2>Order book</h2><Badge tone="neutral">{filtered.length} shown</Badge></div>
          <div className="filter-row">
            <label className="search-field"><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search order, customer or part" /></label>
            <label className="select-field"><Filter /><select value={tier} onChange={(event) => setTier(event.target.value)} aria-label="Filter by customer tier"><option value="ALL">All tiers</option><option>Tier 1</option><option>Tier 2</option><option>Tier 3</option></select></label>
            <label className="select-field"><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by order status"><option value="ALL">All statuses</option><option value="PLANNED">Planned</option><option value="IN_PROGRESS">In progress</option><option value="AT_RISK">At risk</option><option value="DELAYED">Delayed</option></select></label>
          </div>
        </div>
        {filtered.length === 0 ? <EmptyState title="No matching orders" description="Clear one or more filters to return to the full order book." /> : (
          <div className="table-scroll"><table className="orders-table"><thead><tr><th>Order / part</th><th>Customer</th><th>Progress</th><th>Due date</th><th>Delivery confidence</th><th>Revenue / margin</th><th>Status</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{filtered.map((order) => {
            const progress = Math.round(order.completedQty / order.quantity * 100);
            return <tr key={order.id}><td><Link className="table-primary" to={`/orders/${order.id}`}>{order.id}</Link><small>{order.part} · {order.quantity.toLocaleString('en-IN')} pcs</small></td><td>{order.customer}<small>{order.tier}</small></td><td><Progress value={progress} tone="normal" label={`${progress}% complete`} /></td><td>{dateLabel(order.dueDate)}<small>{order.expectedCompletion > order.dueDate ? `Forecast ${dateLabel(order.expectedCompletion)}` : 'On plan'}</small></td><td><strong className={order.deliveryProbability < 75 ? 'text-critical' : order.deliveryProbability < 88 ? 'text-warning' : 'text-healthy'}>{order.deliveryProbability}%</strong><small>{order.risk} risk</small></td><td>{money(order.revenue)}<small>{money(order.margin)} margin</small></td><td><Badge tone={order.status} dot>{order.status.replace('_', ' ')}</Badge></td><td><Link to={`/orders/${order.id}`} className="row-link" aria-label={`Open ${order.id}`}><ArrowRight /></Link></td></tr>;
          })}</tbody></table></div>
        )}
      </Panel>
    </div>
  );
}

export function OrderDetailPage() {
  const { orderId = 'ORD-018' } = useParams();
  const fallback = fallbackOrders.find((order) => order.id === orderId) ?? fallbackOrders[0];
  const { data: order } = useAsyncData(() => api.order(orderId), fallback);
  const progress = Math.round(order.completedQty / order.quantity * 100);
  return (
    <div className="page-stack">
      <div className="detail-back"><Link to="/orders"><ArrowLeft />Back to orders</Link><span>Last recalculated 2 minutes ago</span></div>
      <PageHeader kicker={`${order.tier.toUpperCase()} CUSTOMER · ${order.family}`} title={`${order.id} · ${order.part}`} description={`${order.customer} · ${order.quantity.toLocaleString('en-IN')} pieces · ${order.material}`} actions={<><button className="button button-secondary" onClick={() => window.print()}><Download />Order brief</button><Link className="button button-primary" to={`/schedule?order=${order.id}`}>Show in schedule <ArrowRight /></Link></>} />
      <div className="order-status-band">
        <div><span>Order status</span><Badge tone={order.status} dot>{order.status.replace('_', ' ')}</Badge></div>
        <div><span>Delivery risk</span><SeverityBadge level={order.risk} /></div>
        <div><span>Promise date</span><strong>{dateLabel(order.dueDate)}</strong></div>
        <div><span>Forecast completion</span><strong className={order.expectedCompletion > order.dueDate ? 'text-critical' : ''}>{dateLabel(order.expectedCompletion)}</strong></div>
        <div><span>Delivery confidence</span><strong>{order.deliveryProbability}%</strong></div>
      </div>
      <div className="dashboard-grid order-detail-grid">
        <Panel className="span-8" title="Operation route" eyebrow="FINITE SCHEDULE" action={<Badge tone="neutral">{progress}% complete</Badge>}>
          <div className="operation-timeline">
            {order.operations.map((operation, index) => (
              <div className={`operation-step step-${operation.status.toLowerCase()}`} key={`${operation.name}-${index}`}>
                <div className="operation-marker"><span>{index + 1}</span></div>
                <div className="operation-card">
                  <div className="operation-head"><div><small>OPERATION {String(index + 1).padStart(2, '0')}</small><h3>{operation.name}</h3></div><Badge tone={operation.status}>{operation.status}</Badge></div>
                  <div className="operation-meta"><span><strong>{operation.machine}</strong>Machine</span><span><strong>{operation.start.slice(5)}</strong>Start</span><span><strong>{operation.end.slice(5)}</strong>Finish</span></div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <div className="span-4 side-stack">
          <Panel title="Commercial case" eyebrow="RISK-ADJUSTED">
            <div className="resource-list"><MetricRow label="Order revenue" value={money(order.revenue)} /><MetricRow label="Expected contribution" value={money(order.margin)} tone="healthy" /><MetricRow label="Penalty per late day" value={money(order.penaltyPerDay)} /><MetricRow label="Expected penalty" value={money(order.expectedPenalty)} tone={order.expectedPenalty > 0 ? 'critical' : undefined} /><MetricRow label="Margin after risk" value={money(order.margin - order.expectedPenalty)} /></div>
          </Panel>
          <Panel title="Material readiness" eyebrow={order.material.toUpperCase()} action={<Badge tone={order.materialStatus}>{order.materialStatus}</Badge>}>
            <Progress value={order.materialStatus === 'AVAILABLE' ? 100 : order.materialStatus === 'INCOMING' ? 68 : 28} tone={order.materialStatus === 'SHORTAGE' ? 'critical' : order.materialStatus === 'INCOMING' ? 'warning' : 'healthy'} label="Allocation" />
            <div className="resource-list compact"><MetricRow label="Required" value={`${(order.quantity * 2.4 / 1000).toFixed(2)} tonnes`} /><MetricRow label="Allocated" value={order.materialStatus === 'AVAILABLE' ? '100%' : '64%'} /><MetricRow label="Incoming" value={order.materialStatus === 'AVAILABLE' ? '—' : '03 Sep · 09:00'} /></div>
          </Panel>
        </div>
      </div>
      {order.risk !== 'LOW' && <Panel className="decision-panel" eyebrow="EXPLAINABLE RECOMMENDATION" title="Protect this commitment before adding new grinding work">
        <div className="decision-layout"><div className="decision-icon"><ShieldCheck /></div><div><p><strong>{order.id}</strong> is sequenced ahead of flexible orders because its {money(order.penaltyPerDay, false)}/day penalty and {order.tier} relationship outweigh the extra ₹21,500 overtime recovery cost.</p><div className="inline-actions"><Link className="button button-primary" to="/risks">Review action</Link><Link className="button button-secondary" to="/disruptions">Test breakdown impact</Link></div></div></div>
      </Panel>}
    </div>
  );
}
