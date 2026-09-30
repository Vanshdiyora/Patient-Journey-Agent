import React from "react";
/**
 * PageHeading â€” consistent page header with eyebrow, title, description and
 * optional right-side actions (buttons, filters, etc).
 */
export default function PageHeading({ eyebrow, title, description, actions }) {
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
