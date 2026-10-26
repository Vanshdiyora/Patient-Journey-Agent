import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarDays, ChevronLeft, ChevronRight, Plus, RotateCw, Search } from "lucide-react";
import { calendarApi } from "../services/api";
import { addDays, dateKey, moveAnchor, rangeDays, STATUS_LABELS, viewRange } from "../calendarDates";
import CalendarGrid from "../components/CalendarGrid";
import EventDetails from "../components/EventDetails";
import BookingForm from "../components/BookingForm";
import { useAuth } from "../../../context/AuthContext";
import { useToast } from "../../../context/ToastContext";
import { useAsync } from "../../../hooks/useAsync";
import { ErrorState, PageHeading, Panel, SkeletonRows, TabBar } from "../../../components/index";
import { isPatient, isStaff, portalName } from "../../../utils/roles";

const VIEWS = [{ id: "day", label: "Day" }, { id: "week", label: "Week" }, { id: "month", label: "Month" }];
const emptyFilters = { search: "", patient: "", clinician: "", coordinator: "", journeyStatus: "", status: "", from: "", to: "" };

export default function Calendar() {
  const { user } = useAuth();
  const toast = useToast();
  const [view, setView] = useState("month");
  const [anchor, setAnchor] = useState(dateKey(new Date()));
  const [filters, setFilters] = useState(emptyFilters);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [searchParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState(() => searchParams.get("eventId"));
  const [booking, setBooking] = useState(null);
  const options = useAsync(() => calendarApi.options(), [refresh]);
  const { start, end } = viewRange(anchor, view);
  const filterStart = filters.from ? new Date(`${filters.from}T00:00:00`) : start;
  const filterEnd = filters.to ? addDays(new Date(`${filters.to}T00:00:00`), 1) : end;
  const queryStart = new Date(Math.max(start.getTime(), filterStart.getTime()));
  const queryEnd = new Date(Math.min(end.getTime(), filterEnd.getTime()));
  const invalidRange = filters.from && filters.to && filters.from > filters.to;
  const result = useAsync(() => queryEnd <= queryStart ? Promise.resolve({ items: [], total: 0 }) : calendarApi.events({
    start: queryStart.toISOString(), end: queryEnd.toISOString(), search: filters.search || undefined,
    patient_id: filters.patient || undefined, clinician_id: filters.clinician || undefined, coordinator_id: filters.coordinator || undefined,
    journey_status: filters.journeyStatus || undefined, status: filters.status || undefined,
  }), [queryStart.toISOString(), queryEnd.toISOString(), filters.search, filters.patient, filters.clinician, filters.coordinator, filters.journeyStatus, filters.status, refresh]);
  const set = (key, value) => setFilters(current => ({ ...current, [key]: value }));
  const events = result.data?.items || [];
  const optionData = options.data || { patients: [], staff: [] };
  const title = view === "month" ? new Date(`${anchor}T00:00:00`).toLocaleDateString([], { month: "long", year: "numeric" }) : view === "day" ? start.toLocaleDateString([], { dateStyle: "full" }) : `${start.toLocaleDateString([], { month: "short", day: "numeric" })} – ${addDays(end, -1).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`;
  const changed = async saved => {
    setRefresh(value => value + 1);
    toast.success(saved.status === "CANCELLED" ? "Booking cancelled." : "Schedule saved.");
  };
  return <div className="calendar-page">
    <PageHeading eyebrow={portalName(user)} title={isPatient(user) ? "My calendar" : "Calendar"}
      description={isPatient(user) ? "Your appointments and planned care journey activities." : user.role === "ADMIN" ? "Appointments and pathway activities across all patients." : "Appointments and pathway activities for patients assigned to you."}
      actions={isStaff(user) && <button className="primary-btn" type="button" disabled={options.loading || Boolean(options.error)} onClick={() => setBooking({ event: null })}><Plus size={16} /> Book activity</button>} />
    <Panel className="calendar-panel">
      <div className="calendar-controls">
        <div className="calendar-navigation"><button className="secondary-btn" type="button" onClick={() => { setAnchor(dateKey(new Date())); setFilters(current => ({ ...current, from: "", to: "" })); }}>Today</button><button className="icon-btn" type="button" aria-label={`Previous ${view}`} onClick={() => setAnchor(moveAnchor(anchor, view, -1))}><ChevronLeft size={18} /></button><button className="icon-btn" type="button" aria-label={`Next ${view}`} onClick={() => setAnchor(moveAnchor(anchor, view, 1))}><ChevronRight size={18} /></button><h2 aria-live="polite">{title}</h2></div>
        <div className="calendar-view-controls"><TabBar tabs={VIEWS} active={view} onChange={setView} /><button className="secondary-btn calendar-filter-toggle" type="button" aria-controls="calendar-filters" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(value => !value)}>Filters{Object.values(filters).filter(Boolean).length ? ` (${Object.values(filters).filter(Boolean).length})` : ""}</button><button className="icon-btn" type="button" aria-label="Refresh calendar" onClick={() => setRefresh(value => value + 1)}><RotateCw size={16} /></button></div>
      </div>
      <div id="calendar-filters" className={`calendar-filters ${filtersOpen ? "calendar-filters--open" : ""}`}>
        <label className="calendar-search"><span>Search activities</span><div><Search size={15} /><input type="search" value={filters.search} placeholder="Patient, activity or journey" onChange={e => set("search", e.target.value)} /></div></label>
        {!isPatient(user) && <label>Patient<select value={filters.patient} onChange={e => set("patient", e.target.value)}><option value="">All permitted patients</option>{optionData.patients.map(patient => <option key={patient.id} value={patient.id}>{patient.name} ({patient.reference})</option>)}</select></label>}
        <label>Clinician<select value={filters.clinician} onChange={e => set("clinician", e.target.value)}><option value="">All assigned clinicians</option>{optionData.staff.filter(staff => staff.role === "CLINICIAN").map(staff => <option key={staff.id} value={staff.id}>{staff.name}</option>)}</select></label>
        <label>Care coordinator<select value={filters.coordinator} onChange={e => set("coordinator", e.target.value)}><option value="">All assigned coordinators</option>{optionData.staff.filter(staff => staff.role === "CARE_COORDINATOR").map(staff => <option key={staff.id} value={staff.id}>{staff.name}</option>)}</select></label>
        <label>Journey status<select value={filters.journeyStatus} onChange={e => set("journeyStatus", e.target.value)}><option value="">All journey statuses</option>{["ACTIVE", "BLOCKED", "COMPLETED", "CANCELLED"].map(status => <option key={status} value={status}>{status[0] + status.slice(1).toLowerCase()}</option>)}</select></label>
        <label>Activity status<select value={filters.status} onChange={e => set("status", e.target.value)}><option value="">All activity statuses</option>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>From date<input type="date" value={filters.from} onChange={e => { set("from", e.target.value); if (e.target.value) setAnchor(e.target.value); }} /></label>
        <label>Through date<input type="date" value={filters.to} min={filters.from || undefined} onChange={e => set("to", e.target.value)} /></label>
        <button className="secondary-btn" type="button" onClick={() => setFilters(emptyFilters)}>Clear filters</button>
      </div>
      <div className="calendar-meta"><span><CalendarDays size={15} />{result.loading ? "Loading activities…" : `${events.length} activities in this view`}</span><span>Times in {Intl.DateTimeFormat().resolvedOptions().timeZone}</span></div>
      <div className="calendar-legend" aria-label="Activity status legend">{Object.entries(STATUS_LABELS).map(([value, label]) => <span key={value} className={`calendar-status calendar-status--${value.toLowerCase()}`}>{label}</span>)}<span className="calendar-note">Planned / due dates appear without a booked time.</span></div>
      {options.error && <ErrorState error={options.error} title="Could not load calendar filters" onRetry={options.refetch} />}
      {invalidRange ? <p role="alert" className="form-error">Choose a through date on or after the from date.</p> : result.error ? <ErrorState error={result.error} title="Could not load calendar" onRetry={result.refetch} /> : result.loading ? <SkeletonRows /> : <>
        {!events.length && <p className="calendar-empty" role="status">No activities match this view. Change the date or clear the filters.</p>}
        <CalendarGrid view={view} days={rangeDays(start, end)} events={events} anchor={anchor} onOpen={setSelectedId} onDay={day => { setAnchor(day); setView("day"); }} />
      </>}
    </Panel>
    {selectedId && !booking && <EventDetails id={selectedId} user={user} onClose={() => setSelectedId(null)} onEdit={event => setBooking({ event })} onChanged={changed} />}
    {booking && <BookingForm event={booking.event} options={optionData} anchor={booking.event?.starts_at ? dateKey(booking.event.starts_at) : anchor} onClose={() => setBooking(null)} onSaved={async saved => { await changed(saved); setBooking(null); setSelectedId(saved.id); }} />}
  </div>;
}
