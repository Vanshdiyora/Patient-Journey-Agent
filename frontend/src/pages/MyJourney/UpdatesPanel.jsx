import React from "react";
import { formatDate, humanize } from "../../utils";
import { EmptyState, Panel, SkeletonRows } from "../../components";
import ReportForm from "./ReportForm";

/** Updates the patient has sent, plus the form to send more. */
export default function UpdatesPanel({ events, eventRows, currentId, onSent }) {
  return (
    <Panel title="My updates" subtitle="Messages you've sent">
      {events.loading ? <SkeletonRows /> : eventRows.length ? (
        <div className="event-list">{eventRows.slice(0, 8).map(e => (
          <div className="event-row" key={e.id}>
            <div><strong>{humanize(e.event_type)}</strong><span>{formatDate(e.event_time, true)}</span></div>
            <span className={`event-dot ${e.processed ? "event-dot--done" : ""}`} title={e.processed ? "Reviewed" : "Awaiting review"} />
          </div>
        ))}</div>
      ) : <EmptyState small title="No updates yet" text="Use the form to tell your care team how you're doing." />}
      {currentId && <ReportForm journeyId={currentId} onDone={onSent} />}
    </Panel>
  );
}
