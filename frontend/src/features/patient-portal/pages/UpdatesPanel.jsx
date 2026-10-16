import React from "react";
import { formatDate, humanize } from "../../../utils/index";
import { EmptyState, Panel, SkeletonRows, Pagination, ErrorState } from "../../../components/index";
import ReportForm from "./ReportForm";

/** Updates the patient has sent, plus the form to send more. */
export default function UpdatesPanel({ events, eventRows, currentId, onSent, offset, total, onPage }) {
  return (
    <Panel title="My updates" subtitle="Messages you've sent">
      {events.error ? <ErrorState error={events.error} title="Could not load updates" /> : events.loading ? <SkeletonRows /> : eventRows.length ? (
        <div className="event-list">{eventRows.map(e => (
          <div className="event-row" key={e.id}>
            <div><strong>{humanize(e.event_type)}</strong><span>{formatDate(e.event_time, true)}</span></div>
            <span className={`event-dot ${e.processed ? "event-dot--done" : ""}`} title={e.processed ? "Reviewed" : "Awaiting review"} />
          </div>
        ))}</div>
      ) : <EmptyState small title="No updates yet" text="Use the form to tell your care team how you're doing." />}
      {!events.loading && !events.error && <Pagination offset={offset} count={eventRows.length} total={total ?? 0} onPage={onPage} />}
      {currentId && <ReportForm journeyId={currentId} onDone={onSent} />}
    </Panel>
  );
}
