import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown } from "lucide-react";

/**
 * Custom styled dropdown replacing the native <select> across the app.
 *
 * - Trigger is a plain button in normal document flow (no wrapper positioning
 *   requirements).
 * - Option list is portal-rendered to <body> with fixed positioning, so it is
 *   never clipped by panels (`overflow:hidden`) or stacking contexts.
 * - Flips above the trigger when there is more room above than below.
 * - Keyboard: Enter/Space/ArrowDown open; Esc closes; ArrowUp/Down/Home/End
 *   navigate; Enter/Space/Tab pick; type-ahead jumps to a matching option.
 */
export default function Select({
  value,
  onChange,
  options = [],
  label,
  placeholder = "Select…",
  disabled = false,
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [up, setUp] = useState(false);
  const triggerRef = useRef(null);
  const listRef = useRef(null);
  const typeAhead = useRef({ q: "", ts: 0 });

  const valueIndex = options.findIndex(o => (o?.value ?? "") === (value ?? ""));

  const close = useCallback(() => {
    setOpen(false);
    setActive(-1);
  }, []);

  const toggle = useCallback(() => {
    if (disabled) return;
    setOpen(o => !o);
  }, [disabled]);

  // On open: start keyboard navigation at the selected option (or the first).
  useEffect(() => {
    if (!open) return;
    setUp(false); // reset before measuring
    setActive(valueIndex >= 0 ? valueIndex : 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Measure available space and position the portal list once it is in the DOM.
  const position = useCallback(() => {
    const trigger = triggerRef.current;
    const list = listRef.current;
    if (!trigger || !list) return;
    const r = trigger.getBoundingClientRect();
    const spaceAbove = r.top;
    const spaceBelow = window.innerHeight - r.bottom;
    const flip = spaceBelow < list.offsetHeight + 12 && spaceAbove > spaceBelow;
    setUp(flip);
    const width = Math.max(r.width, list.scrollWidth);
    const left = Math.min(r.left, window.innerWidth - width - 8);
    list.style.left = `${Math.max(8, left)}px`;
    list.style.width = `${width}px`;
    if (flip) {
      list.style.top = "auto";
      list.style.bottom = `${window.innerHeight - r.top + 6}px`;
    } else {
      list.style.bottom = "auto";
      list.style.top = `${r.bottom + 6}px`;
    }
  }, []);

  useLayoutEffect(() => {
    if (open) position();
  }, [open, position]);

  // Re-measure after paint (list height can settle once fonts/layout settle).
  useEffect(() => {
    if (!open) return;
    const raf = requestAnimationFrame(position);
    window.addEventListener("resize", position);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", position);
    };
  }, [open, position]);

  // Close on outside pointerdown.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (!triggerRef.current?.contains(e.target) && !listRef.current?.contains(e.target)) close();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open, close]);

  // Close when the page scrolls: a fixed-position list would visually detach
  // from its trigger while scrolling.
  useEffect(() => {
    if (!open) return;
    const onScroll = (e) => {
      if (listRef.current?.contains(e.target)) return; // scrolling the options is fine
      close();
    };
    window.addEventListener("scroll", onScroll, true);
    return () => window.removeEventListener("scroll", onScroll, true);
  }, [open, close]);

  // Scroll the active option into view.
  useEffect(() => {
    if (!open || active < 0) return;
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const pick = useCallback((idx) => {
    const opt = options[idx];
    if (!opt || opt.disabled) return;
    onChange?.(opt.value);
    close();
    triggerRef.current?.focus();
  }, [options, onChange, close]);

  const onKeyDown = (e) => {
    if (disabled) return;
    if (!open) {
      if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(e.key)) {
        e.preventDefault();
        toggle();
      }
      return;
    }

    switch (e.key) {
      case "Escape":
      case "Tab":
        close(); // Tab closes but lets focus move naturally
        break;
      case "ArrowDown":
        e.preventDefault();
        setActive(a => Math.min(a + 1, options.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive(a => Math.max(a - 1, 0));
        break;
      case "Home":
        e.preventDefault();
        setActive(0);
        break;
      case "End":
        e.preventDefault();
        setActive(options.length - 1);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        pick(active);
        break;
      default: {
        // Type-ahead: jump to the next option starting with the pressed keys.
        const ch = e.key.length === 1 ? e.key.toLowerCase() : "";
        if (!ch) break;
        e.preventDefault();
        const now = Date.now();
        const ta = typeAhead.current;
        ta.q = now - ta.ts > 500 ? ch : ta.q + ch;
        ta.ts = now;
        const indices = [...options.keys()];
        const order = indices.slice(active + 1).concat(indices.slice(0, active + 1));
        const hit = order.find(i => String(options[i].label ?? "").toLowerCase().startsWith(ta.q));
        if (hit != null) setActive(hit);
      }
    }
  };

  const selected = valueIndex >= 0 ? options[valueIndex] : null;
  // Empty value + a `label` prop: show the label as the trigger text so
  // toolbar filters read "All statuses", "All priorities", etc.
  const display = selected?.label ?? (value ? value : label ?? placeholder);

  return (
    <div className={`select-root ${className}`.trim()}>
      <button
        type="button"
        ref={triggerRef}
        className="select-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label || undefined}
        onKeyDown={onKeyDown}
        onClick={toggle}
      >
        <span className={`select-value ${!selected && label ? "select-value--muted" : ""}`}>{display}</span>
        <ChevronDown size={15} className={`select-chevron ${open ? "select-chevron--open" : ""}`} />
      </button>

      {open && createPortal(
        <ul
          ref={listRef}
          className={`select-list ${up ? "select-list--up" : ""}`}
          role="listbox"
          aria-label={label || undefined}
        >
          {options.map((opt, i) => (
            <li
              key={opt.value}
              data-index={i}
              role="option"
              aria-selected={i === valueIndex}
              aria-disabled={opt.disabled || undefined}
              className={[
                "select-option",
                i === active ? "select-option--active" : "",
                i === valueIndex ? "select-option--selected" : "",
                opt.disabled ? "select-option--disabled" : "",
              ].filter(Boolean).join(" ")}
              onPointerEnter={() => !opt.disabled && setActive(i)}
              onClick={() => pick(i)}
            >
              <span className="select-option-label">{opt.label}</span>
              {i === valueIndex && <Check size={14} className="select-option-check" />}
            </li>
          ))}
        </ul>,
        document.body
      )}
    </div>
  );
}
