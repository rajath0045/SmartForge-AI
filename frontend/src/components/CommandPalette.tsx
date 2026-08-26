import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ArrowRight, Command, Search, X, type LucideIcon } from 'lucide-react';

export interface CommandPaletteItem {
  group: string;
  icon: LucideIcon;
  label: string;
  to: string;
  description?: string;
}

interface CommandPaletteProps {
  items: CommandPaletteItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (to: string) => void;
}

// Interaction model adapted from the HextaUI Command Menu on 21st.dev.
export function CommandPalette({ items, open, onOpenChange, onSelect }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const reduceMotion = useReducedMotion();
  const filtered = useMemo(() => {
    const search = query.trim().toLowerCase();
    return search
      ? items.filter((item) => `${item.label} ${item.group} ${item.description ?? ''}`.toLowerCase().includes(search))
      : items;
  }, [items, query]);

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, [onOpenChange, open]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    setQuery('');
    setActiveIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  useEffect(() => {
    setActiveIndex((index) => Math.min(index, Math.max(0, filtered.length - 1)));
  }, [filtered.length]);

  function choose(to: string) {
    onSelect(to);
    onOpenChange(false);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') onOpenChange(false);
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => filtered.length ? (index + 1) % filtered.length : 0);
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((index) => filtered.length ? (index - 1 + filtered.length) % filtered.length : 0);
    }
    if (event.key === 'Enter' && filtered[activeIndex]) choose(filtered[activeIndex].to);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="command-overlay"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => { if (event.target === event.currentTarget) onOpenChange(false); }}
        >
          <motion.div
            className="command-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="SmartForge command palette"
            initial={reduceMotion ? false : { opacity: 0, y: -14, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.99 }}
            transition={{ duration: 0.16, ease: 'easeOut' }}
          >
            <div className="command-input-row">
              <Search />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search pages, decisions, and factory workflows…"
                aria-label="Search SmartForge"
              />
              <button onClick={() => onOpenChange(false)} aria-label="Close command palette"><X /></button>
            </div>
            <div className="command-context">
              <span><Command /> Plant 01 command center</span>
              <span>{filtered.length} destinations</span>
            </div>
            <div className="command-list" role="listbox">
              {filtered.length === 0 ? (
                <div className="command-empty"><Search /><strong>No matching workflow</strong><span>Try “schedule”, “risk”, or “profit”.</span></div>
              ) : filtered.map((item, index) => {
                const Icon = item.icon;
                const showGroup = index === 0 || filtered[index - 1].group !== item.group;
                return (
                  <div key={item.to}>
                    {showGroup && <div className="command-group-label">{item.group}</div>}
                    <button
                      role="option"
                      aria-selected={activeIndex === index}
                      className={activeIndex === index ? 'active' : ''}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => choose(item.to)}
                    >
                      <span className="command-icon"><Icon /></span>
                      <span><strong>{item.label}</strong><small>{item.description ?? 'Open workspace'}</small></span>
                      <ArrowRight />
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span><span><kbd>↵</kbd> Open</span><span><kbd>esc</kbd> Close</span></div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
