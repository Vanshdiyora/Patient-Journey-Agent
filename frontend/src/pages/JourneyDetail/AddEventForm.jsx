import React, { useState } from "react";
import { Send } from "lucide-react";
import { Select } from "../../components";

const EVENT_TYPES = [
  { value: "GENERAL_UPDATE", label: "General update" },
  { value: "SYMPTOM_REPORTED", label: "Symptom reported" },
  { value: "QUESTION_ASKED", label: "Question asked" },
  { value: "APPOINTMENT_PREFERENCE", label: "Appointment preference" },
  { value: "DOCUMENT_UPLOADED", label: "Document uploaded" },
  { value: "MEDICATION_TAKEN", label: "Medication taken" },
  { value: "VITALS_RECORDED", label: "Vitals recorded" },
  { value: "ATTENDANCE_CONFIRMED", label: "Attendance confirmed" },
  { value: "TASK_COMPLETED", label: "Task completed (reported)" },
  { value: "STATUS_REPORT", label: "Status report" },
];

/** Staff-side event submission form (journey detail page). */
export default function AddEventForm({ busy, onAdd }) {
  const [eventType, setEventType] = useState(EVENT_TYPES[0].value);
  const [details, setDetails] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const added = await onAdd({
      event_type: eventType,
      source: "carepath-ui",
      event_time: new Date().toISOString(),
      payload: { comment: details.trim() },
    });
    if (added) setDetails("");
  };

  return (
    <form className="event-form" onSubmit={submit}>
      <div className="event-form-title"><Send size={14} /> Add event</div>
      <label>
        Event type
        <Select
          label="Event type"
          value={eventType}
          onChange={setEventType}
          options={EVENT_TYPES}
          disabled={busy}
        />
      </label>
      <label>
        Details
        <textarea
          required
          maxLength="2000"
          value={details}
          onChange={e => setDetails(e.target.value)}
          rows="3"
          placeholder="Describe the update for the care team…"
          disabled={busy}
        />
      </label>
      <button className="primary-btn" disabled={busy || !details.trim()}>{busy ? "Adding…" : "Add event"}</button>
      <p className="event-form-note">Adding an event records an update; it does not by itself mark a journey step complete.</p>
    </form>
  );
}
