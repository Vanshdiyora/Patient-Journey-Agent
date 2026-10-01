import React, { useState } from "react";
import { Send } from "lucide-react";
import { meApi } from "../../services";
import { getErrorMessage } from "../../utils";
import { AlertBanner, Select } from "../../components";
import { useConfirm } from "../../components/ConfirmModal";
import { useToast } from "../../context/ToastContext";

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
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();

  const submit = async (e) => {
    e.preventDefault();
    const ok = await confirm({
      title: "Send this update?",
      message: `Your ${eventType === "QUESTION_ASKED" ? "question" : "update"} will be delivered to your care team for review.`,
      confirmLabel: "Send update",
      intent: "primary",
    });
    if (!ok) return;
    setBusy(true);
    setFeedback(null);
    try {
      await meApi.submitEvent(journeyId, { event_type: eventType, payload: { comment } });
      setFeedback({ tone: "success", text: "Thank you — your update was sent to your care team for review." });
      toast.success("Update sent to your care team.");
      setComment("");
      onDone?.();
    } catch (err) {
      const text = getErrorMessage(err);
      setFeedback({ tone: "error", text });
      toast.error(text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="event-form" onSubmit={submit}>
      <div className="event-form-title"><Send size={14} /> Send an update</div>
      <Select value={eventType} onChange={setEventType} options={EVENT_TYPES} />
      <textarea value={comment} onChange={e => setComment(e.target.value)} rows="3" placeholder="Tell your care team how you're doing…" />
      {feedback && <AlertBanner tone={feedback.tone}>{feedback.text}</AlertBanner>}
      <button className="primary-btn" disabled={busy || !comment.trim()}>{busy ? "Sending…" : "Send update"}</button>
      <p style={{ fontSize: 9, color: "#899592", margin: 0 }}>
        Updates are reviewed by your care team and do not change your treatment plan directly.
      </p>
      {confirmModal}
    </form>
  );
}
