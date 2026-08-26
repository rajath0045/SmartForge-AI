import { useEffect } from 'react';
import { motion, useReducedMotion, useSpring, useTransform } from 'motion/react';

// Adapted for SmartForge from the Build UI Animated Counter published on 21st.dev.
function AnimatedCounter({ value, decimals }: { value: number; decimals: number }) {
  const reduceMotion = useReducedMotion();
  const spring = useSpring(value, { stiffness: 92, damping: 24, mass: 0.72 });
  const display = useTransform(spring, (latest) => new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(latest));

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  if (reduceMotion) {
    return <>{new Intl.NumberFormat('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value)}</>;
  }

  return <motion.span>{display}</motion.span>;
}

export function AnimatedMetric({ value }: { value: string }) {
  const match = value.match(/[-+]?\d[\d,]*(?:\.\d+)?/);
  if (!match || match.index === undefined) return <>{value}</>;

  const rawNumber = match[0];
  const numericValue = Number(rawNumber.replaceAll(',', ''));
  if (!Number.isFinite(numericValue)) return <>{value}</>;

  const decimals = rawNumber.includes('.') ? rawNumber.split('.')[1].length : 0;
  const prefix = value.slice(0, match.index);
  const suffix = value.slice(match.index + rawNumber.length);

  return (
    <span className="animated-metric" aria-label={value}>
      <span aria-hidden="true">{prefix}</span>
      <span aria-hidden="true"><AnimatedCounter value={numericValue} decimals={decimals} /></span>
      <span aria-hidden="true">{suffix}</span>
    </span>
  );
}
