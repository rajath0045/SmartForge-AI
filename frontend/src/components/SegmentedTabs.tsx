import { useId } from 'react';
import { motion, useReducedMotion } from 'motion/react';

export interface SegmentedTab<T extends string> {
  label: string;
  value: T;
  count?: number;
}

// Compact analytical variant of the animated tabs pattern published on 21st.dev.
export function SegmentedTabs<T extends string>({ items, value, onChange, label }: {
  items: SegmentedTab<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  const id = useId();
  const reduceMotion = useReducedMotion();
  return (
    <div className="industrial-tabs" role="tablist" aria-label={label}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button key={item.value} role="tab" aria-selected={active} onClick={() => onChange(item.value)}>
            {active && <motion.span className="industrial-tab-active" layoutId={`industrial-tab-${id}`} transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 430, damping: 34 }} />}
            <span className="industrial-tab-label">{item.label}{item.count !== undefined && <small>{item.count}</small>}</span>
          </button>
        );
      })}
    </div>
  );
}
