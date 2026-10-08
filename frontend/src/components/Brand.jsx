import React from "react";

/** Brand mark shared by the sidebar and authentication pages. */
export default function Brand({ withText = false }) {
  return (
    <>
      <div className="brand-mark" role="img" aria-label="Patient Journey logo">
        <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path d="M6 24h3c3 0 3-6 7-6h2c3 0 4-2 4-3.5" />
          <circle cx="6" cy="24" r="2" />
          <path d="m22 14.5-4.25-4.25a2.75 2.75 0 0 1 3.89-3.89l.36.36.36-.36a2.75 2.75 0 0 1 3.89 3.89L22 14.5Z" />
        </svg>
      </div>
      {withText && <div><strong>Patient Journey</strong></div>}
    </>
  );
}
