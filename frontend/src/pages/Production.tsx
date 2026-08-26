import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, CalendarDays, Check, ChevronDown, CircleAlert, Clock3, Filter, Languages, Maximize2, Play, Printer, RotateCcw, Search, UserRound } from 'lucide-react';
import { machines, orders, scheduleTasks as fallbackTasks } from '../data/demo';
import { boardTranslations, type BoardLanguage } from '../i18n/board';
import { useAsyncData } from '../hooks';
import { api } from '../services/api';
import type { ScheduleTask } from '../types';
import { Badge, PageHeader, Panel } from '../components/UI';

const days = ['Tue 01', 'Wed 02', 'Thu 03', 'Fri 04', 'Sat 05', 'Sun 06', 'Mon 07', 'Tue 08', 'Wed 09', 'Thu 10', 'Fri 11', 'Sat 12', 'Sun 13', 'Mon 14'];

export function SchedulePage() {
  const { data: tasks } = useAsyncData(api.schedule, fallbackTasks);
  const [params] = useSearchParams();
  const initialOrder = params.get('order') ?? 'ALL';
  const [tier, setTier] = useState('ALL');
  const [machineType, setMachineType] = useState('ALL');
  const [order, setOrder] = useState(initialOrder);
  const [riskOnly, setRiskOnly] = useState(false);
  const [selected, setSelected] = useState<ScheduleTask | null>(null);
  const visibleMachines = useMemo(() => machines.filter((machine) => machineType === 'ALL' || machine.type.includes(machineType)), [machineType]);
  const filteredTasks = useMemo(() => tasks.filter((task) => (tier === 'ALL' || task.tier === tier) && (order === 'ALL' || task.orderId === order) && (!riskOnly || task.status === 'AT_RISK')), [tasks, tier, order, riskOnly]);

  return (
    <div className="page-stack schedule-page">
      <PageHeader kicker="FINITE CAPACITY SCHEDULE · 01–14 SEP" title="Two-week production plan" description="Machine-level operations with changeovers, maintenance and risk status. Each bar is placed against finite shift capacity." actions={<><button className="button button-secondary" onClick={() => window.print()}><Printer />Print plan</button><Link to="/disruptions" className="button button-primary">Inject disruption <ArrowRight /></Link></>} />
      <div className="schedule-summary"><div><span className="summary-dot production" /><strong>Production</strong><span>54 operations</span></div><div><span className="summary-dot changeover" /><strong>Changeover</strong><span>5 setups</span></div><div><span className="summary-dot maintenance" /><strong>Maintenance</strong><span>3 windows</span></div><div><span className="summary-dot risk" /><strong>At risk</strong><span>2 operations</span></div><div className="schedule-valid"><Check /><strong>Schedule validated</strong><span>No machine conflicts · precedence passed</span></div></div>
      <Panel className="gantt-panel flush-panel">
        <div className="gantt-toolbar">
          <div className="filter-row">
            <label className="select-field"><Filter /><select value={machineType} onChange={(event) => setMachineType(event.target.value)}><option value="ALL">All resources</option><option value="CNC">CNC lathes</option><option value="Milling">Milling</option><option value="Drilling">Drilling</option><option value="Grinding">Grinding</option><option value="Inspection">Inspection</option></select></label>
            <label className="select-field"><select value={tier} onChange={(event) => setTier(event.target.value)}><option value="ALL">All tiers</option><option>Tier 1</option><option>Tier 2</option><option>Tier 3</option></select></label>
            <label className="select-field"><Search /><select value={order} onChange={(event) => setOrder(event.target.value)}><option value="ALL">All orders</option>{orders.map((item) => <option key={item.id}>{item.id}</option>)}</select></label>
            <label className="checkbox-filter"><input type="checkbox" checked={riskOnly} onChange={(event) => setRiskOnly(event.target.checked)} />At-risk only</label>
          </div>
          <button className="icon-button" aria-label="Reset schedule filters" title="Reset filters" onClick={() => { setMachineType('ALL'); setTier('ALL'); setOrder('ALL'); setRiskOnly(false); }}><RotateCcw /></button>
        </div>
        <div className="gantt-scroll">
          <div className="gantt-canvas">
            <div className="gantt-header-row"><div className="gantt-machine-header">MACHINE / LOAD</div><div className="gantt-days">{days.map((day, index) => <div key={day} className={index === 5 || index === 12 ? 'sunday' : ''}><strong>{day}</strong><span>S1&nbsp;&nbsp;&nbsp;&nbsp;S2</span></div>)}</div></div>
            {visibleMachines.map((machine) => {
              const machineTasks = filteredTasks.filter((task) => task.machineId === machine.id);
              return <div className="gantt-row" key={machine.id}><div className="gantt-machine"><div><strong>{machine.id}</strong><span>{machine.type}</span></div><Badge tone={machine.utilization >= 90 ? 'critical' : machine.utilization >= 80 ? 'warning' : 'healthy'}>{machine.utilization}%</Badge></div><div className="gantt-track">{days.map((day, index) => <span key={day} className={`day-grid ${index === 5 || index === 12 ? 'sunday' : ''}`} style={{ left: `${index / 14 * 100}%`, width: `${100 / 14}%` }} />)}<span className="now-line" style={{ left: '1.2%' }}><i>NOW</i></span>{machineTasks.map((task) => <button key={task.id} className={`gantt-task kind-${task.kind.toLowerCase()} task-${task.status.toLowerCase()}`} style={{ left: `${((task.day * 24 + task.startHour) / (14 * 24)) * 100}%`, width: `${Math.max(1.25, (task.duration / (14 * 24)) * 100)}%` }} onClick={() => setSelected(task)} title={`${task.orderId} · ${task.operation}`}><strong>{task.kind === 'PRODUCTION' ? task.orderId : task.operation}</strong><span>{task.operation}</span></button>)}</div></div>;
            })}
          </div>
        </div>
      </Panel>
      {selected && <div className="task-drawer" role="dialog" aria-modal="true" aria-label="Schedule operation detail"><button className="drawer-scrim" onClick={() => setSelected(null)} aria-label="Close operation detail" /><div className="drawer-card"><div className="drawer-top"><div><span className="eyebrow">SCHEDULE OPERATION</span><h2>{selected.orderId}</h2></div><button className="icon-button" onClick={() => setSelected(null)} aria-label="Close"><ChevronDown /></button></div><Badge tone={selected.status}>{selected.status}</Badge><div className="drawer-operation"><span>{selected.operation}</span><strong>{selected.machineId}</strong></div><div className="resource-list"><div className="metric-row"><span>Customer priority</span><strong>{selected.tier}</strong></div><div className="metric-row"><span>Planned day</span><strong>{days[selected.day]}</strong></div><div className="metric-row"><span>Shift time</span><strong>{selected.startHour < 8 ? 'Shift 1' : 'Shift 2'} · {selected.duration} h</strong></div><div className="metric-row"><span>Constraint status</span><strong className="text-healthy">Validated</strong></div></div><Link className="button button-primary full-button" to={`/orders/${selected.orderId}`}>Open order <ArrowRight /></Link></div></div>}
    </div>
  );
}

type BoardJob = { machine: string; type: string; time: string; end: string; order: string; part: string; qty: number; status: 'running' | 'ready' | 'setup' | 'held'; issue?: string };
const boardJobs: BoardJob[] = [
  { machine: 'GRIND-01', type: 'Cylindrical Grinder', time: '06:00', end: '09:00', order: 'ORD-003', part: 'AX-204', qty: 380, status: 'running', issue: 'Check wheel dressing at 08:30' },
  { machine: 'CNC-L01', type: 'CNC Lathe', time: '06:00', end: '10:20', order: 'ORD-007', part: 'SH-208', qty: 620, status: 'running' },
  { machine: 'CNC-L02', type: 'CNC Lathe', time: '06:00', end: '11:30', order: 'ORD-012', part: 'GB-118', qty: 440, status: 'running' },
  { machine: 'MILL-01', type: 'VMC Milling', time: '06:30', end: '10:00', order: 'ORD-018', part: 'AX-204', qty: 280, status: 'running', issue: 'Priority job — send directly to grinding queue' },
  { machine: 'MILL-02', type: 'VMC Milling', time: '07:00', end: '11:15', order: 'ORD-021', part: 'BR-420', qty: 510, status: 'ready' },
  { machine: 'DRILL-01', type: 'Drilling', time: '06:00', end: '09:40', order: 'ORD-009', part: 'SP-331', qty: 760, status: 'setup', issue: 'First-piece inspection required' },
  { machine: 'INSPECT-01', type: 'Quality Inspection', time: '06:00', end: '08:45', order: 'ORD-004', part: 'SH-208', qty: 360, status: 'ready' },
  { machine: 'CNC-L03', type: 'CNC Lathe', time: '06:00', end: '10:00', order: 'ORD-014', part: 'PN-744', qty: 900, status: 'held', issue: 'Material not released — wait for supervisor' },
];

export function TodayBoardPage() {
  const [language, setLanguage] = useState<BoardLanguage>('en');
  const [jobs, setJobs] = useState(boardJobs);
  const t = boardTranslations[language];
  function advance(machine: string) { setJobs((current) => current.map((job) => job.machine === machine ? { ...job, status: job.status === 'running' ? 'ready' : 'running' } : job)); }
  return (
    <div className="page-stack today-page">
      <PageHeader kicker={`${t.shift.toUpperCase()} · 06:00–14:00 · TUE 01 SEP`} title={t.title} description={t.subtitle} actions={<><label className="language-select"><Languages /><select value={language} onChange={(event) => setLanguage(event.target.value as BoardLanguage)} aria-label="Board language"><option value="en">English</option><option value="kn">ಕನ್ನಡ</option><option value="ta">தமிழ்</option></select></label><button className="button button-secondary" onClick={() => window.print()}><Printer />Print</button></>} />
      <div className="board-summary"><div><span className="board-big green">6</span><span><strong>{t.running}</strong><small>{t.machine}</small></span></div><div><span className="board-big amber">2</span><span><strong>{t.setup}</strong><small>{t.machine}</small></span></div><div><span className="board-big red">1</span><span><strong>{t.held}</strong><small>{t.machine}</small></span></div><div className="supervisor-note"><UserRound /><span><strong>{t.supervisor}</strong><small>{t.note}</small></span></div></div>
      <div className="production-board-grid">{jobs.map((job) => <article key={job.machine} className={`production-card card-${job.status}`}><div className="machine-strip"><div><small>{t.machine}</small><h2>{job.machine}</h2><span>{job.type}</span></div><Badge tone={job.status} dot>{t[job.status]}</Badge></div><div className="job-time"><Clock3 /><span><strong>{job.time}</strong><small>START</small></span><ArrowRight /><span><strong>{job.end}</strong><small>END</small></span></div><div className="job-main"><span><small>{t.order}</small><strong>{job.order}</strong></span><span><small>{t.part}</small><strong>{job.part}</strong></span><span><small>{t.quantity}</small><strong>{job.qty} {t.pieces}</strong></span></div><div className={`issue-line ${job.issue ? 'has-issue' : ''}`}>{job.issue ? <CircleAlert /> : <Check />}<span><small>{t.issue}</small><strong>{job.issue ?? t.noIssue}</strong></span></div><button className={`board-action action-${job.status}`} disabled={job.status === 'held'} onClick={() => advance(job.machine)}>{job.status === 'running' ? <><Check />{t.complete}</> : <><Play />{t.start}</>}</button></article>)}</div>
    </div>
  );
}
