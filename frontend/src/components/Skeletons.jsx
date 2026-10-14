import React from "react";
/**
 * SkeletonRows / DetailSkeleton â€” shimmering placeholders shown while data loads.
 */
export function SkeletonRows({ count = 6 }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: count }).map((_, i) => (
        <div className="skeleton-row" key={i}><i /><i /><i /><i /></div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return <div className="skeleton-detail"><i /><i /><i /></div>;
}

export function MetricCardSkeleton() {
  return <div className="metric-card metric-card--skeleton" aria-hidden="true">
    <div className="metric-icon metric-skeleton-icon" />
    <div className="metric-copy metric-skeleton-copy">
      <i className="metric-skeleton-label" />
      <i className="metric-skeleton-value" />
      <i className="metric-skeleton-hint" />
    </div>
    <i className="metric-skeleton-arrow" />
  </div>;
}
