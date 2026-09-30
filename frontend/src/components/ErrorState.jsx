import React from "react";
import { getErrorMessage } from "../utils";

/**
 * ErrorState â€” friendly failure message for a failed data fetch,
 * with an optional Retry button (pass onRetry wired to refetch).
 */
export default function ErrorState({ error, title = "Something went wrong", onRetry }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{getErrorMessage(error)}</span>
      {onRetry && <button className="secondary-btn" onClick={onRetry}>Retry</button>}
    </div>
  );
}
