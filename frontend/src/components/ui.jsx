/** Small shared UI primitives used across feature pages. */

import React from "react";

import { Activity, ArrowUpRight, ChevronLeft, ChevronRight } from "lucide-react";

import { getErrorMessage, statusClass, priorityClass, severityClass, humanize } from "../utils";

/**
 * AlertBanner â€” inline feedback banner after actions (evaluate/orchestrate/events).
 */
export function AlertBanner({ tone = "error", children }) {
  return (
    <div className={`alert-banner ${tone === "success" ? "alert-banner--success" : "alert-banner--error"}`}>
      <Activity size={18} />
      <span>{children}</span>
    </div>
  );
}

/**
 * Badge â€” colored pill for status / priority / severity values.
 */
export function Badge({ kind = "status", value, fallback }) {
  const cls =
    kind === "priority" ? priorityClass(value) :
    kind === "severity" ? severityClass(value) :
    statusClass(value);
  return <span className={cls}>{fallback || humanize(value)}</span>;
}

/**
 * EmptyState â€” "nothing here" placeholder with icon, title, and hint text.
 */
export function EmptyState({ icon: Icon, title, text, small = false }) {
  return (
    <div className={`empty-state ${small ? "empty-state--small" : ""}`.trim()}>
      {Icon && <Icon size={small ? 24 : 30} />}
      <strong>{title}</strong>
      {text && <span>{text}</span>}
    </div>
  );
}

/**
 * ErrorState â€” friendly failure message for a failed data fetch,
 * with an optional Retry button (pass onRetry wired to refetch).
 */
export function ErrorState({ error, title = "Something went wrong", onRetry }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{getErrorMessage(error)}</span>
      {onRetry && <button className="secondary-btn" onClick={onRetry}>Retry</button>}
    </div>
  );
}

/**
 * JsonView â€” pretty-printed JSON block.
 */
export function JsonView({ data, maxHeight }) {
  return (
    <pre className="json-view" style={maxHeight ? { maxHeight } : undefined}>
      {JSON.stringify(data ?? {}, null, 2)}
    </pre>
  );
}

/**
 * MetricCard â€” dashboard KPI card with icon, label, value and hint.
 */
export function MetricCard({ icon: Icon, label, value, hint, tone = "teal" }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon metric-icon--${tone}`}><Icon size={20} /></div>
      <div className="metric-copy">
        <span>{label}</span>
        <strong>{value ?? "â€”"}</strong>
        {hint && <small>{hint}</small>}
      </div>
      <ArrowUpRight size={17} className="metric-arrow" />
    </div>
  );
}

/**
 * PageHeading â€” consistent page header with eyebrow, title, description and
 * optional right-side actions (buttons, filters, etc).
 */
export function PageHeading({ eyebrow, title, description, actions }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="button-group">{actions}</div>}
    </div>
  );
}

export function Pagination({ offset, limit = 10, count = 0, total = count, onPage }) {
  if (total <= limit && offset === 0) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="pagination">
      <span>{total ? `${offset + 1}-${offset + count} of ${total} results` : "0 results"}</span>
      <div>
        <button className="icon-btn" type="button" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))} aria-label="Previous page"><ChevronLeft size={17} /></button>
        <span aria-live="polite">Page {page} of {pages}</span>
        <button className="icon-btn" type="button" disabled={offset + count >= total} onClick={() => onPage(offset + limit)} aria-label="Next page"><ChevronRight size={17} /></button>
      </div>
    </div>
  );
}

/**
 * Panel â€” the bordered card container used across every page.
 * Renders an optional header (title + subtitle + optional action link/node)
 * and always renders children as the panel body.
 */
export function Panel({ title, subtitle, action, headerIcon: HeaderIcon, wide = false, className = "", children }) {
  return (
    <section className={`panel ${wide ? "panel--wide" : ""} ${className}`.trim()}>
      {(title || action) && (
        <div className="panel-header">
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {HeaderIcon && <HeaderIcon size={18} />}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * TabBar — accessible tab strip shared by My Journey and Patients.
 * Purely presentational: selection state lives in the parent via `active` /
 * `onChange` (see hooks/useTabs).
 */
export function TabBar({ tabs, active, onChange, className = "" }) {
  return (
    <div className={`tab-bar ${className}`.trim()} role="tablist">
      {tabs.map(({ id, label, icon: Icon, count }) => (
        <button key={id} role="tab" aria-selected={active === id}
          className={`tab-btn ${active === id ? "tab-btn--active" : ""}`}
          onClick={() => onChange(id)}>
          {Icon && <Icon size={15} />}
          {label}
          {count != null && count > 0 && <span className="tab-count">{count}</span>}
        </button>
      ))}
    </div>
  );
}
