import React, { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarDays } from "lucide-react";
import { calendarApi } from "../services/api";
import { useAsync } from "../../../hooks/useAsync";
import { useConfirm } from "../../../components/ConfirmModal";
import { ErrorState, SkeletonRows } from "../../../components/index";
import { getErrorMessage, humanize } from "../../../utils/index";
import { isPatient } from "../../../utils/roles";
import CalendarDialog from "./CalendarDialog";
import { STATUS_LABELS } from "../calendarDates";

export default function EventDetails({ id, user, onClose, onEdit, onChanged }) {
  const result = useAsync(() => calendarApi.event(id), [id]);
  const [confirm, confirmation] = useConfirm();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const event = result.data;
  const cancel = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const approved = await confirm({ title: "Cancel this booking?", message: `Cancel ${event.activity} for ${event.patient_name}? The care journey activity will remain in the care plan.`, confirmLabel: "Cancel booking", intent: "danger" });
      if (!approved) return;
      const saved = await calendarApi.cancel(event.id, { revision: event.revision, confirmed: true });
      await onChanged(saved);
      await result.refetch();
    } catch (cause) { setError(getErrorMessage(cause)); }
    finally { setBusy(false); }
  };
  return <>
    <CalendarDialog title="Journey activity" onClose={onClose} busy={busy}>
      {result.loading ? <SkeletonRows /> : result.error ? <ErrorState error={result.error} onRetry={result.refetch} /> : event && <>
        <div className="calendar-detail-heading"><span className={`calendar-status calendar-status--${event.status.toLowerCase()}`}>{STATUS_LABELS[event.status]}</span><h3>{event.activity}</h3><p>{event.journey_name} · {humanize(event.activity_type)}</p></div>
        <div className="detail-list">
          <div className="detail-row"><span>Patient</span><Link className="table-link" to={`/patients/${event.patient_id}`}>{event.patient_name} ({event.patient_reference})</Link></div>
          <div className="detail-row"><span>{event.all_day ? "Target date" : "Starts"}</span><strong>{event.starts_at ? new Date(event.starts_at).toLocaleString([], event.all_day ? { dateStyle: "full" } : { dateStyle: "medium", timeStyle: "short" }) : "Not scheduled"}</strong></div>
          {!event.all_day && <div className="detail-row"><span>Ends</span><strong>{new Date(event.ends_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</strong></div>}
          <div className="detail-row"><span>Assigned to activity</span><strong>{event.assigned_staff ? `${event.assigned_staff.name} · ${humanize(event.assigned_staff.role)}` : "To be assigned"}</strong></div>
          {event.care_team.map(staff => <div className="detail-row" key={staff.id}><span>{humanize(staff.role)}</span><strong>{staff.name}{!staff.is_active && " (inactive)"}</strong></div>)}
          <div className="detail-row"><span>Activity status</span><strong>{humanize(event.step_status)}</strong></div>
          <div className="detail-row"><span>Journey status</span><strong>{humanize(event.journey_status)}</strong></div>
          <div className="detail-row"><span>Journey progress</span><strong>{event.journey_progress.completed} / {event.journey_progress.total} completed · {event.journey_progress.pending} pending</strong></div>
        </div>
        {event.description && <p className="calendar-detail-description">{event.description}</p>}
        {event.all_day && <p className="calendar-note"><CalendarDays size={16} />{event.date_source === "DEADLINE" ? "This is the activity deadline. An appointment time has not been booked." : "This is a planned pathway date. An appointment time has not been booked."}</p>}
        {event.conflict_count > 0 && <p className="calendar-conflict"><AlertTriangle size={16} />{event.conflict_count} overlapping activity or activities in your patient scope.</p>}
        {error && <div className="form-error" role="alert">{error}</div>}
        <footer className="calendar-dialog-actions">
          <Link className="secondary-btn" to={isPatient(user) ? `/my-journey?journeyId=${event.journey_id}` : `/journeys/${event.journey_id}`}>View journey</Link>
          {event.can_manage && <button className="primary-btn" type="button" disabled={busy} onClick={() => onEdit(event)}>{event.all_day ? "Book activity" : event.status === "CANCELLED" ? "Book again" : "Edit / reschedule"}</button>}
          {event.can_manage && !event.all_day && event.status !== "CANCELLED" && <button className="danger-btn" type="button" disabled={busy} onClick={cancel}>Cancel booking</button>}
        </footer>
      </>}
    </CalendarDialog>
    {confirmation}
  </>;
}
