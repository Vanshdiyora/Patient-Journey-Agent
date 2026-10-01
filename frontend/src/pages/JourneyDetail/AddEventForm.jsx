import React, { useState } from "react";
import { AlertTriangle, Send } from "lucide-react";

/** Staff-side event submission form (journey detail page). */
export default function AddEventForm({ busy, onAdd }) {
  const [eventType, setEventType] = useState("");
  const [eventSource, setEventSource] = useState("carepath-ui");
  const [eventPayload, setEventPayload] = useState("{}");
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    let payload = {};
    try { payload = JSON.parse(eventPayload || "{}"); }
    catch {
      setError("Event payload must be valid JSON.");
      return;
    }
    setError("");
    await onAdd({ event_type: eventType.trim(), source: eventSource.trim(), event_time: new Date().toISOString(), payload });
    setEventType("");
    setEventPayload("{}");
  };

  return (
    <form className="event-form" onSubmit={submit}>
      <div className="event-form-title"><Send size={14} /> Add event</div>
      <div className="event-form-grid">
        <input required value={eventType} onChange={e => setEventType(e.target.value)} placeholder="Event type" />
        <input required value={eventSource} onChange={e => setEventSource(e.target.value)} placeholder="Source" />
      </div>
      <textarea value={eventPayload} onChange={e => setEventPayload(e.target.value)} rows="4" spellCheck="false" placeholder='{"key":"value"}' />
      {error && <div className="event-form-error"><AlertTriangle size={13} /> {error}</div>}
      <button className="primary-btn" disabled={busy}>{busy ? "Adding…" : "Add event"}</button>
    </form>
  );
}
