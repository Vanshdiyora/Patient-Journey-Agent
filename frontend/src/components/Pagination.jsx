import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function Pagination({ offset, limit = 10, count = 0, total = count, onPage }) {
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
