import { useId, useState, type ReactNode } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ArrowDownRight, ArrowUpRight, ChevronDown, Info } from 'lucide-react';
import { AnimatedMetric } from './AnimatedMetric';

type Tone = 'default' | 'profit' | 'danger' | 'warning' | 'healthy' | string;

function deterministicSeries(seed: string, trend = 0) {
  let hash = 17;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return Array.from({ length: 12 }, (_, index) => {
    const wave = Math.sin((index + hash % 5) * .78) * 8;
    const drift = index * Math.max(-1.2, Math.min(1.2, trend / 12));
    return 48 + wave + drift + ((hash + index * 7) % 9);
  });
}

function Sparkline({ seed, trend = 0, tone }: { seed: string; trend?: number; tone: Tone }) {
  const values = deterministicSeries(seed, trend);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const points = values.map((value, index) => `${index / (values.length - 1) * 120},${32 - ((value - min) / Math.max(1, max - min)) * 27}`).join(' ');
  return (
    <svg className={`metric-sparkline spark-${tone}`} viewBox="0 0 120 36" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" vectorEffect="non-scaling-stroke" />
      <line x1="0" y1="34" x2="120" y2="34" />
    </svg>
  );
}

export interface PremiumMetricCardProps {
  label: string;
  value: string;
  detail?: string;
  trend?: number;
  trendLabel?: string;
  comparison?: string;
  tone?: Tone;
  icon?: ReactNode;
  onActivate?: () => void;
}

// Adapted from 21st.dev Progress Metric, Trend Card, and animated statistics-card patterns.
export function PremiumMetricCard({ label, value, detail, trend, trendLabel, comparison, tone = 'default', icon, onActivate }: PremiumMetricCardProps) {
  const reduceMotion = useReducedMotion();
  const positive = (trend ?? 0) >= 0;
  const Component = onActivate ? motion.button : motion.div;
  return (
    <Component
      className={`premium-metric-card kpi-card kpi-${tone}`}
      data-tone={tone}
      onClick={onActivate}
      tabIndex={0}
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={reduceMotion ? undefined : { y: -3 }}
      transition={{ duration: reduceMotion ? 0 : .3, ease: [0.22, 1, 0.36, 1] }}
      aria-label={`${label}: ${value}${detail ? `. ${detail}` : ''}`}
    >
      <div className="kpi-top"><span>{label}</span>{icon && <span className="kpi-icon">{icon}</span>}</div>
      <strong className="kpi-value"><AnimatedMetric value={value} /></strong>
      <Sparkline seed={`${label}-${value}`} trend={trend} tone={tone} />
      <div className="kpi-detail">
        {trend !== undefined && <span className={positive ? 'trend-positive' : 'trend-negative'}>{positive ? <ArrowUpRight /> : <ArrowDownRight />}{Math.abs(trend)}%</span>}
        <span>{trendLabel ?? detail}</span>
      </div>
      {comparison && <span className="metric-comparison">{comparison}</span>}
      <span className="metric-hover-detail" role="tooltip"><Info />{detail ?? trendLabel ?? 'Current planning horizon'}</span>
    </Component>
  );
}

export interface TimeRangeItem<T extends string> { value: T; label: string; }

export function TimeRangeSelector<T extends string>({ value, items, onChange, label = 'Time range' }: { value: T; items: Array<TimeRangeItem<T>>; onChange: (value: T) => void; label?: string }) {
  const id = useId();
  const reduceMotion = useReducedMotion();
  return <div className="time-range" role="tablist" aria-label={label}>{items.map((item) => <button key={item.value} role="tab" aria-selected={value === item.value} onClick={() => onChange(item.value)}>{value === item.value && <motion.span className="time-range-active" layoutId={`range-${id}`} transition={{ duration: reduceMotion ? 0 : .2 }} />}<span>{item.label}</span></button>)}</div>;
}

export function LiveStatusIndicator({ label, detail, tone = 'healthy' }: { label: string; detail?: string; tone?: 'healthy' | 'warning' | 'critical' | 'neutral' }) {
  return <span className={`live-status live-${tone}`}><i /><span><strong>{label}</strong>{detail && <small>{detail}</small>}</span></span>;
}

export function RadialMeter({ value, label, tone = 'healthy', size = 58 }: { value: number; label?: string; tone?: 'healthy' | 'warning' | 'critical' | 'neutral'; size?: number }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - Math.min(100, Math.max(0, value)) / 100 * circumference;
  return <span className={`radial-meter radial-${tone}`} style={{ width: size, height: size }} aria-label={`${label ?? 'Score'}: ${value}%`}><svg viewBox="0 0 48 48" aria-hidden="true"><circle className="radial-track" cx="24" cy="24" r={radius} /><motion.circle className="radial-value" cx="24" cy="24" r={radius} initial={{ strokeDashoffset: circumference }} animate={{ strokeDashoffset: offset }} transition={{ duration: .75, ease: [0.22, 1, .36, 1] }} style={{ strokeDasharray: circumference }} /></svg><strong>{Math.round(value)}</strong>{label && <small>{label}</small>}</span>;
}

type TooltipEntry = { name?: string; value?: unknown; color?: string; dataKey?: string | number };

export function ChartTooltip({ active, payload, label, formatter }: { active?: boolean; payload?: TooltipEntry[]; label?: ReactNode; formatter?: (value: number, name: string) => string }) {
  if (!active || !payload?.length) return null;
  return <div className="premium-chart-tooltip">{label !== undefined && <strong>{label}</strong>}{payload.map((entry, index) => { const name = entry.name ?? String(entry.dataKey ?? 'Value'); const numeric = Number(entry.value ?? 0); return <div key={`${name}-${index}`}><i style={{ background: entry.color ?? '#c9aa73' }} /><span>{name}</span><strong>{formatter ? formatter(numeric, name) : numeric.toLocaleString('en-IN')}</strong></div>; })}</div>;
}

export function InteractiveChartCard({ title, eyebrow, insight, action, children, details, className = '' }: { title: string; eyebrow?: string; insight?: string; action?: ReactNode; children: ReactNode; details?: ReactNode; className?: string }) {
  const [expanded, setExpanded] = useState(false);
  const reduceMotion = useReducedMotion();
  return <motion.section className={`panel interactive-chart-card ${className}`} layout={!reduceMotion}><div className="panel-heading"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2>{title}</h2></div><div className="chart-card-actions">{action}{details && <button className="analytics-expand" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}><span>{expanded ? 'Less' : 'Insight'}</span><ChevronDown /></button>}</div></div><div className="interactive-chart-body">{children}</div>{insight && <p className="chart-insight"><Info />{insight}</p>}<AnimatePresence initial={false}>{expanded && details && <motion.div className="analytics-details" initial={reduceMotion ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>{details}</motion.div>}</AnimatePresence></motion.section>;
}

export function ExpandableAnalyticsPanel({ title, eyebrow, summary, children, defaultOpen = false, className = '' }: { title: string; eyebrow?: string; summary?: string; children: ReactNode; defaultOpen?: boolean; className?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  const reduceMotion = useReducedMotion();
  return <section className={`panel expandable-analytics ${open ? 'is-open' : ''} ${className}`}><button className="expandable-heading" onClick={() => setOpen((value) => !value)} aria-expanded={open}><span>{eyebrow && <small>{eyebrow}</small>}<strong>{title}</strong>{summary && <em>{summary}</em>}</span><ChevronDown /></button><AnimatePresence initial={false}>{open && <motion.div className="expandable-content" initial={reduceMotion ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>{children}</motion.div>}</AnimatePresence></section>;
}

export function InsightCard({ icon, label, value, detail, tone = 'neutral' }: { icon?: ReactNode; label: string; value: string; detail: string; tone?: string }) {
  return <article className={`insight-card insight-${tone}`} tabIndex={0}>{icon && <span>{icon}</span>}<div><small>{label}</small><strong>{value}</strong><p>{detail}</p></div></article>;
}
