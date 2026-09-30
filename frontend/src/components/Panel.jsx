import React from "react";
/**
 * Panel â€” the bordered card container used across every page.
 * Renders an optional header (title + subtitle + optional action link/node)
 * and always renders children as the panel body.
 */
export default function Panel({ title, subtitle, action, headerIcon: HeaderIcon, wide = false, className = "", children }) {
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
