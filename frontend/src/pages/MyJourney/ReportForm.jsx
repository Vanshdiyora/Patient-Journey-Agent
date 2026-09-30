import React, { useState } from "react";
import { Send } from "lucide-react";
import { meApi } from "../../services";
import { getErrorMessage } from "../../utils";
import { AlertBanner } from "../../components";

/** Event types the patient portal allows the care team to receive. */
export const EVENT_TYPES = [
  { value: "SYMPTOM_REPORTED", label: "Report a symptom" },
  { value: "APPOINTMENT_PREFERENCE", label: "Appointment preference" },
  { value: "DOCUMENT_UPLOADED", label: "Document uploaded" },
  { value: "GENERAL_UPDATE", label: "General update" },
  { value: "QUESTION_ASKED", label: "Question for my care team" },
];

/** Patient-submitted update form. Patient-safe payload only: the backend
 * strips anything else and forces source/verified server-side. */
export default function ReportForm({ journeyId, onDone }) {
  const [eventType, setEventType] = useState("SYMPTOM_REPORTED");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      await meApi.submitEvent(journeyId, { event_type: eventType, payload: { comment } });
      setFeedback({ tone: "success", text: "Thank you — your update was sent to your care team for review." });
      setComment("");
      onDone?.();
    } catch (err) {
      setFeedback({ tone: "error", text: getErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="event-form" onSubmit={submit}>
      <div className="event-form-title"><Send size={14} /> Send an update</div>
      <select value={eventType} onChange={e => setEventType(e.target.value)} style={{ padding: "8px 9px", borderRadius: 7, border: "1px solid #e0e6e4", fontSize: 11 }}>
        {EVENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>
      <textarea value={comment} onChange={e => setComment(e.target.value)} rows="3" placeholder="Tell your care team how you're doing…" />
      {feedback && <AlertBanner tone={feedback.tone}>{feedback.text}</AlertBanner>}
      <button className="primary-btn" disabled={busy || !comment.trim()}>{busy ? "Sending…" : "Send update"}</button>
      <p style={{ fontSize: 9, color: "#899592", margin: 0 }}>
        Updates are reviewed by your care team and do not change your treatment plan directly.
      </p>
    </form>
  );
}
