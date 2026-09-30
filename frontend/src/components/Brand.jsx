import React from "react";
/**
 * Brand â€” logo mark + optional wordmark, reused by the sidebar and login page.
 */
export default function Brand({ withText = false }) {
  return (
    <>
      <div className="brand-mark"><span>+</span></div>
      {withText && <div><strong>Patient</strong><small>Journey Orchestrator</small></div>}
    </>
  );
}
