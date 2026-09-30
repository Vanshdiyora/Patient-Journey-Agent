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
