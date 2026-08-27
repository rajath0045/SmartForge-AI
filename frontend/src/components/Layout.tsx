import { Suspense, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import {
  Activity, AlertTriangle, BarChart3, BatteryCharging, Bell, Boxes, CalendarRange, ChevronLeft, ChevronRight,
  ChevronDown, CircleDollarSign, ClipboardCheck, Factory, Gauge, HardHat, LayoutDashboard, Menu, RadioTower, Search,
  Settings2, ShieldAlert, Sparkles, UsersRound, Wrench, X, Zap,
} from 'lucide-react';
import type { ConnectionMode } from '../types';
import { Badge, LoadingState } from './UI';
import { CommandPalette, type CommandPaletteItem } from './CommandPalette';

interface NavEntry { label: string; to: string; icon: typeof Factory; }
interface NavGroup { label: string; entries: NavEntry[]; }

const navGroups: NavGroup[] = [
  { label: 'COMMAND', entries: [
    { label: 'Control Tower', to: '/control-tower', icon: RadioTower },
    { label: 'Executive', to: '/dashboard', icon: LayoutDashboard },
    { label: 'Risks & actions', to: '/risks', icon: ShieldAlert },
  ]},
  { label: 'PLAN', entries: [
    { label: 'Orders', to: '/orders', icon: ClipboardCheck },
    { label: 'Order acceptance', to: '/acceptance', icon: Sparkles },
    { label: 'Production plan', to: '/schedule', icon: CalendarRange },
    { label: 'Capacity', to: '/capacity', icon: Gauge },
    { label: 'Plan comparison', to: '/plan-comparison', icon: BarChart3 },
  ]},
  { label: 'OPERATE', entries: [
    { label: "Today's board", to: '/today', icon: Boxes },
    { label: 'Disruptions', to: '/disruptions', icon: AlertTriangle },
    { label: 'Scenarios', to: '/scenarios', icon: Settings2 },
  ]},
  { label: 'RESOURCES', entries: [
    { label: 'Machines', to: '/machines', icon: Wrench },
    { label: 'Machine health', to: '/machine-health', icon: Activity },
    { label: 'Workforce', to: '/workforce', icon: UsersRound },
    { label: 'Energy', to: '/energy', icon: BatteryCharging },
    { label: 'Profitability', to: '/profitability', icon: CircleDollarSign },
  ]},
];

const allEntries = navGroups.flatMap((group) => group.entries);
const commandDescriptions: Record<string, string> = {
  '/control-tower': 'Live management queue and factory pulse',
  '/dashboard': 'Executive delivery, utilization, and financial KPIs',
  '/risks': 'Prioritized problems, exposure, and corrective actions',
  '/orders': 'Committed production orders and delivery confidence',
  '/acceptance': 'Evaluate an RFQ against finite capacity',
  '/schedule': 'Machine-level two-week production schedule',
  '/capacity': 'Constraint load and available-to-promise capacity',
  '/plan-comparison': 'Compare cost, service, and robustness trade-offs',
  '/today': 'Shift-ready operator production board',
  '/disruptions': 'Inject an event and generate a recovery plan',
  '/scenarios': 'Test operational and investment scenarios',
  '/machines': 'Machine state, utilization, and capabilities',
  '/machine-health': 'Failure risk and preventive maintenance signals',
  '/workforce': 'Shift coverage and skill qualification matrix',
  '/energy': 'Power availability and generator economics',
  '/profitability': 'Order contribution and risk-adjusted margin',
};
const commandItems: CommandPaletteItem[] = navGroups.flatMap((group) => group.entries.map((entry) => ({
  ...entry,
  group: group.label,
  description: commandDescriptions[entry.to],
})));

export function AppLayout({ connection }: { connection: ConnectionMode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => Object.fromEntries(navGroups.map((group) => [group.label, true])));
  const location = useLocation();
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();
  const current = allEntries.find((entry) => location.pathname === entry.to || (entry.to !== '/' && location.pathname.startsWith(`${entry.to}/`)));

  function chooseResult(to: string) {
    navigate(to);
  }

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`} aria-label="Primary navigation">
        <div className="brand-row">
          <Link to="/control-tower" className="brand" onClick={() => setMobileOpen(false)}>
            <span className="brand-mark"><Factory /></span>
            {!collapsed && <span><strong>OptiForge</strong><small>SMARTFORGE OPERATIONS</small></span>}
          </Link>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X /></button>
        </div>
        <div className="plant-chip">
          <span className="plant-avatar">SP</span>
          {!collapsed && <span><strong>Sridhar Precision Works</strong><small>Hosur · Plant 01</small></span>}
        </div>
        <nav className="nav-scroll">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              {!collapsed && <button className="nav-label" type="button" aria-expanded={openGroups[group.label]} onClick={() => setOpenGroups((current) => ({ ...current, [group.label]: !current[group.label] }))}><span>{group.label}</span><ChevronDown /></button>}
              {(collapsed || openGroups[group.label]) && group.entries.map((entry) => {
                const Icon = entry.icon;
                return (
                  <NavLink key={entry.to} to={entry.to} title={collapsed ? entry.label : undefined} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <Icon /><span>{entry.label}</span>
                    {entry.to === '/risks' && !collapsed && <span className="nav-count">4</span>}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {!collapsed && <div className="live-pulse"><span /><div><strong>Shop model synced</strong><small>Updated 42 sec ago</small></div></div>}
          <button className="collapse-button" onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            {collapsed ? <ChevronRight /> : <ChevronLeft />}{!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>
      {mobileOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu /></button>
            <div className="breadcrumb"><span>Plant 01</span><ChevronRight /><strong>{current?.label ?? 'SmartForge'}</strong></div>
          </div>
          <div className="topbar-right">
            <button className="global-search command-trigger" onClick={() => setCommandOpen(true)} aria-label="Open command palette">
              <Search />
              <span>Search plant workflows…</span>
              <kbd>⌘K</kbd>
            </button>
            <button className="icon-button mobile-command" onClick={() => setCommandOpen(true)} aria-label="Search plant workflows"><Search /></button>
            <Badge tone={connection === 'live' ? 'healthy' : connection === 'demo' ? 'warning' : 'neutral'} dot>
              {connection === 'live' ? 'Live API' : connection === 'demo' ? 'Demo data' : 'Connecting'}
            </Badge>
            <div className="shift-status"><Zap /><span><strong>Grid stable</strong><small>Shift 1 · 06:00–14:00</small></span></div>
            <Link to="/risks" className="icon-button notification-button" aria-label="4 actions require attention"><Bell /><span>4</span></Link>
            <div className="user-chip"><span>RK</span><div><strong>Raj Kumar</strong><small>Plant Manager</small></div></div>
          </div>
        </header>
        <div className="operations-strip" aria-label="Current operating context">
          <div className="operations-strip-title"><RadioTower /><span><strong>Live operating context</strong><small>Tue 01 Sep · Shift 1</small></span></div>
          <div><i className="signal signal-good" /><span>Schedule</span><strong>Validated</strong></div>
          <div><i className="signal signal-critical" /><span>Constraint</span><strong>GRIND-01 · 96.2%</strong></div>
          <div><i className="signal signal-warning" /><span>Decision queue</span><strong>3 due before 10:00</strong></div>
          <div><i className="signal signal-good" /><span>Model</span><strong>Synced 42 sec ago</strong></div>
        </div>
        <motion.main
          className="main-content"
          key={location.pathname}
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.32, ease: [0.22, 1, 0.36, 1] }}
        >
          <Suspense fallback={<LoadingState label="Loading workspace" />}><Outlet /></Suspense>
        </motion.main>
        <footer className="app-footer"><span>SmartForge planning model · Seed 42</span><span>Last validated schedule: 01 Sep 2026, 08:44</span></footer>
      </div>
      <CommandPalette items={commandItems} open={commandOpen} onOpenChange={setCommandOpen} onSelect={chooseResult} />
    </div>
  );
}
