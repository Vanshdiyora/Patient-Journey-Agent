import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Pagination â€” offset-based pager footer used by list pages.
 */
export default function Pagination({ offset, limit, count, onPage }) {
  const prev = () => onPage(Math.max(0, offset - limit));
  const next = () => onPage(offset + limit);
  return (
    <div className="pagination">
      <span>{count ? `${offset + 1}â€“${offset + count}` : "0"} results</span>
      <div>
        <button className="icon-btn" disabled={offset === 0} onClick={prev} aria-label="Previous page"><ChevronLeft size={17} /></button>
        <button className="icon-btn" disabled={count < limit} onClick={next} aria-label="Next page"><ChevronRight size={17} /></button>
      </div>
    </div>
  );
}
