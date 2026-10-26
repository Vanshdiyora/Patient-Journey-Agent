import React, { useState } from "react";
import { calendarApi } from "../services/api";
import { localInput } from "../calendarDates";
import { useAsync } from "../../../hooks/useAsync";
import { useConfirm } from "../../../components/ConfirmModal";
import { getErrorMessage, humanize } from "../../../utils/index";
import CalendarDialog from "./CalendarDialog";

export default function BookingForm({ event, options, anchor, onClose, onSaved }) {
  const [patientId, setPatientId] = useState(event?.patient_id || "");
  const [stepId, setStepId] = useState(event?.id || "");
  const [startsAt, setStartsAt] = useState(event?.starts_at && !event.all_day ? localInput(event.starts_at) : `${anchor}T09:00`);
  const [endsAt, setEndsAt] = useState(event?.ends_at && !event.all_day ? localInput(event.ends_at) : `${anchor}T09:30`);
  const [staffId, setStaffId] = useState(event?.assigned_staff?.id || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, confirmation] = useConfirm();
  const details = useAsync(() => patientId ? calendarApi.options(patientId) : Promise.resolve({ activities: [], staff: [] }), [patientId]);
  const activities = details.data?.activities || [];
  const activity = activities.find(item => item.id === stepId);
  const editing = event && !event.all_day;
  const submit = async submitEvent => {
    submitEvent.preventDefault();
    if (busy || !stepId || details.loading || details.error) return;
    setError("");
    const start = new Date(startsAt), end = new Date(endsAt);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) {
      setError("Choose an end time after the start time."); return;
    }
    // A DST gap can normalize an unavailable local wall time silently.
    if (localInput(start) !== startsAt || localInput(end) !== endsAt) {
      setError("This local time does not exist because the clocks change. Choose another time."); return;
    }
    setBusy(true);
    try {
      const patientName = options.patients.find(patient => patient.id === patientId)?.name || event?.patient_name;
      const approved = await confirm({ title: editing ? "Save scheduling changes?" : "Create this booking?", message: `${event?.activity || activity?.name} for ${patientName}, ${start.toLocaleString()} to ${end.toLocaleString()}.`, confirmLabel: editing ? "Save changes" : "Create booking", intent: "primary" });
      if (!approved) return;
      const payload = { starts_at: start.toISOString(), ends_at: end.toISOString(), assigned_staff_id: staffId || null, revision: event?.revision ?? activity.revision, confirmed: true };
      const saved = editing ? await calendarApi.update(stepId, payload) : await calendarApi.create({ ...payload, journey_step_id: stepId });
      await onSaved(saved);
    } catch (cause) { setError(getErrorMessage(cause)); }
    finally { setBusy(false); }
  };
  return <>
    <CalendarDialog title={editing ? "Edit activity booking" : "Book journey activity"} onClose={onClose} busy={busy}>
      <form className="calendar-booking-form" onSubmit={submit}>
        <p className="calendar-note">Times are in {Intl.DateTimeFormat().resolvedOptions().timeZone}. Availability is checked when you save.</p>
        <label>Patient<select aria-label="Patient" required value={patientId} disabled={busy || Boolean(event)} onChange={e => { setPatientId(e.target.value); setStepId(""); setStaffId(""); }}><option value="">Select patient</option>{options.patients.map(patient => <option key={patient.id} value={patient.id}>{patient.name} ({patient.reference})</option>)}</select></label>
        <label>Journey activity<select aria-label="Journey activity" required value={stepId} disabled={busy || !patientId || details.loading || Boolean(event)} onChange={e => setStepId(e.target.value)}><option value="">{details.loading ? "Loading activities…" : "Select activity"}</option>{event ? <option value={event.id}>{event.activity} · {event.journey_name}</option> : activities.filter(item => !item.booked).map(item => <option key={item.id} value={item.id}>{item.name} · {item.journey_name}</option>)}</select></label>
        {patientId && !details.loading && !details.error && !event && !activities.some(item => !item.booked) && <p className="calendar-note">No unbooked activities are available. Open an existing calendar event to reschedule it.</p>}
        <div className="calendar-form-times"><label>Starts<input required type="datetime-local" value={startsAt} disabled={busy} onChange={e => setStartsAt(e.target.value)} /></label><label>Ends<input required type="datetime-local" value={endsAt} disabled={busy} onChange={e => setEndsAt(e.target.value)} /></label></div>
        <label>Assigned clinician or care coordinator<select aria-label="Assigned clinician or care coordinator" value={staffId} disabled={busy || !patientId || details.loading} onChange={e => setStaffId(e.target.value)}><option value="">To be assigned</option>{(details.data?.staff || []).filter(staff => staff.is_active).map(staff => <option key={staff.id} value={staff.id}>{staff.name} · {humanize(staff.role)}</option>)}</select></label>
        {details.error && <div className="form-error" role="alert">{getErrorMessage(details.error)}</div>}
        {error && <div className="form-error" role="alert">{error}</div>}
        <footer className="calendar-dialog-actions"><button className="secondary-btn" type="button" disabled={busy} onClick={onClose}>Close</button><button className="primary-btn" type="submit" disabled={busy || details.loading || Boolean(details.error) || !stepId}>{busy ? "Saving…" : editing ? "Review changes" : "Review booking"}</button></footer>
      </form>
    </CalendarDialog>
    {confirmation}
  </>;
}
