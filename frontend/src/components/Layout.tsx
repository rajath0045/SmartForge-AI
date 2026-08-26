import { Suspense, useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, AlertTriangle, BarChart3, BatteryCharging, Bell, Boxes, CalendarRange, ChevronLeft, ChevronRight,
  CircleDollarSign, ClipboardCheck, Factory, Gauge, HardHat, LayoutDashboard, Menu, RadioTower, Search,
  Settings2, ShieldAlert, Sparkles, UsersRound, Wrench, X, Zap,
} from 'lucide-react';
import type { ConnectionMode } from '../types';
import { Badge, LoadingState } from './UI';

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

export function AppLayout({ connection }: { connection: ConnectionMode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState('');
  const location = useLocation();
  const navigate = useNavigate();
  const current = allEntries.find((entry) => location.pathname === entry.to || (entry.to !== '/' && location.pathname.startsWith(`${entry.to}/`)));
  const searchResults = useMemo(() => search.trim().length > 1
    ? allEntries.filter((entry) => entry.label.toLowerCase().includes(search.toLowerCase())).slice(0, 5)
    : [], [search]);

  function chooseResult(to: string) {
    setSearch('');
    navigate(to);
  }

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`} aria-label="Primary navigation">
        <div className="brand-row">
          <Link to="/control-tower" className="brand" onClick={() => setMobileOpen(false)}>
            <span className="brand-mark"><Factory /></span>
            {!collapsed && <span><strong>SmartForge</strong><small>DECISION SUPPORT</small></span>}
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
              {!collapsed && <div className="nav-label">{group.label}</div>}
              {group.entries.map((entry) => {
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
            <div className="global-search">
              <Search />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a page…" aria-label="Find a page" onKeyDown={(event) => { if (event.key === 'Enter' && searchResults[0]) chooseResult(searchResults[0].to); }} />
              <kbd>⌘K</kbd>
              {searchResults.length > 0 && <div className="search-results">{searchResults.map((result) => <button key={result.to} onClick={() => chooseResult(result.to)}><result.icon />{result.label}<ChevronRight /></button>)}</div>}
            </div>
            <Badge tone={connection === 'live' ? 'healthy' : connection === 'demo' ? 'warning' : 'neutral'} dot>
              {connection === 'live' ? 'Live API' : connection === 'demo' ? 'Demo data' : 'Connecting'}
            </Badge>
            <div className="shift-status"><Zap /><span><strong>Grid stable</strong><small>Shift 1 · 06:00–14:00</small></span></div>
            <Link to="/risks" className="icon-button notification-button" aria-label="4 actions require attention"><Bell /><span>4</span></Link>
            <div className="user-chip"><span>RK</span><div><strong>Raj Kumar</strong><small>Plant Manager</small></div></div>
          </div>
        </header>
        <main className="main-content"><Suspense fallback={<LoadingState label="Loading workspace" />}><Outlet /></Suspense></main>
        <footer className="app-footer"><span>SmartForge planning model · Seed 42</span><span>Last validated schedule: 01 Sep 2026, 08:44</span></footer>
      </div>
    </div>
  );
}
