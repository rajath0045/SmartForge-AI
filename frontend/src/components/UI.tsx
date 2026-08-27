import type { ReactNode } from 'react';
import { ChevronRight, CircleAlert, LoaderCircle } from 'lucide-react';
import type { RiskLevel } from '../types';
import { PremiumMetricCard } from './Analytics';

export function money(value: number, compact = true): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value);
}

export function dateLabel(value: string): string {
  const date = new Date(`${value.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(date);
}

export function Badge({ children, tone = 'neutral', dot = false }: { children: ReactNode; tone?: string; dot?: boolean }) {
  return (
    <span className={`badge badge-${tone.toLowerCase().replaceAll(' ', '-')}`}>
      {dot && <span className="badge-dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function SeverityBadge({ level }: { level: RiskLevel }) {
  return <Badge tone={level} dot>{level}</Badge>;
}

export function Panel({ children, className = '', title, eyebrow, action, id, tabIndex }: { children: ReactNode; className?: string; title?: string; eyebrow?: string; action?: ReactNode; id?: string; tabIndex?: number }) {
  return (
    <section className={`panel ${className}`} id={id} tabIndex={tabIndex}>
      {(title || eyebrow || action) && (
        <div className="panel-heading">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h2>{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, description, kicker, actions }: { title: string; description: string; kicker?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        {kicker && <div className="page-kicker">{kicker}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
      <span className="page-header-signal" aria-hidden="true"><i /><i /><i /></span>
    </header>
  );
}

export function KpiCard({ label, value, detail, trend, trendLabel, tone = 'default', icon }: { label: string; value: string; detail?: string; trend?: number; trendLabel?: string; tone?: string; icon?: ReactNode }) {
  return <PremiumMetricCard label={label} value={value} detail={detail} trend={trend} trendLabel={trendLabel} tone={tone} icon={icon} />;
}

export function Progress({ value, tone, label }: { value: number; tone?: string; label?: string }) {
  const resolvedTone = tone ?? (value >= 94 ? 'critical' : value >= 82 ? 'warning' : 'healthy');
  return (
    <div className="progress-wrap" aria-label={label ? `${label}: ${value}%` : `${value}%`}>
      <div className="progress-track"><span className={`progress-fill fill-${resolvedTone}`} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} /></div>
      {label && <span className="progress-value">{value.toFixed(1)}%</span>}
    </div>
  );
}

export function MetricRow({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return <div className="metric-row"><span>{label}</span><strong className={tone ? `text-${tone}` : ''}>{value}</strong></div>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><CircleAlert /><strong>{title}</strong><p>{description}</p></div>;
}

export function LoadingState({ label = 'Loading factory data' }: { label?: string }) {
  return <div className="loading-state"><div className="loading-orbit"><LoaderCircle className="spin" /></div><strong>{label}</strong><span>Synchronizing schedule, resources, and risk signals</span><div className="loading-skeleton"><i /><i /><i /></div></div>;
}

export function LinkArrow() {
  return <ChevronRight className="link-arrow" aria-hidden="true" />;
}
