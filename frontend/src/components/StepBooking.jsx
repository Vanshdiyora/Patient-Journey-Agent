import React from "react";
import { Link } from "react-router-dom";
import { formatDate, humanize } from "../utils/index";

export default function StepBooking({ step }) {
  if (!step.scheduled_start_at) return null;
  return <span>Booking: {formatDate(step.scheduled_start_at, true)} – {formatDate(step.scheduled_end_at, true)} · {humanize(step.schedule_status)}{step.scheduled_staff_name && ` · ${step.scheduled_staff_name}`} · <Link className="table-link" to={`/calendar?eventId=${step.id}`}>Calendar</Link></span>;
}
