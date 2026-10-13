import React, { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CalendarDays, ChevronRight, ClipboardList, Network, UserRound } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { journeysApi, patientsApi } from "../services";
import { useAsync } from "../hooks/useAsync";
import { formatDate, getErrorMessage, initials, humanize, toList } from "../utils";
import { Panel, EmptyState, ErrorState, Badge, DetailSkeleton, Select, Pagination, SkeletonRows } from "../components";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import DurationInput from "../components/DurationInput";
import { milestoneLabel } from "../utils/duration";
import { isAdmin } from "../utils/roles";
import DoctorAssignDrawer from "./Patients/DoctorAssignDrawer";

function Detail({ label, value }) {
  return <div className="detail-row"><span>{label}</span><strong>{value || "—"}</strong></div>;
}

const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const ACTIVE_JOURNEY_STATUSES = new Set(["ACTIVE", "BLOCKED"]);

export default function PatientDetail() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isClinician = user?.role === "CLINICIAN";
  const canStartJourney = isClinician || isAdmin(user);
  const { patientId } = useParams();
  const [journeyOffset, setJourneyOffset] = useState(0);
  useEffect(() => { setJourneyOffset(0); }, [patientId]);
  const patient = useAsync(() => patientsApi.get(patientId), [patientId]);
  const journeys = useAsync(() => patientsApi.journeys(patientId, { limit: 10, offset: journeyOffset }), [patientId, journeyOffset]);
  const pathways = useAsync(() => journeysApi.availablePathways(), []);
  const toast = useToast();
  const [pathwayId, setPathwayId] = useState("");
  const [timeLimits, setTimeLimits] = useState({});
  const [priority, setPriority] = useState("MEDIUM");
  const [priorityDrafts, setPriorityDrafts] = useState({});
  const [prioritySavingId, setPrioritySavingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [doctorAssignOpen, setDoctorAssignOpen] = useState(false);
  const closeDoctorAssign = useCallback(() => setDoctorAssignOpen(false), []);
  const p = patient.data;
  const js = toList(journeys.data, "items");
  const hasActiveJourney = Boolean(journeys.data?.has_active_journey);
  const pathwayRows = toList(pathways.data);
  const selectedPathway = pathwayRows.find(pathway => pathway.id === pathwayId);

  const choosePathway = (id) => {
    setPathwayId(id);
    const selected = pathwayRows.find(pathway => pathway.id === id);
    setTimeLimits(Object.fromEntries(
      (selected?.steps || []).map(step => [
        step.id,
        step.time_limit_hours ?? Math.max(step.due_after_days || 1, 1) * 24,
      ])
    ));
  };

  const startJourney = async (event) => {
    event.preventDefault();
    if (!pathwayId || busy || hasActiveJourney || journeys.loading || journeys.error) return;
    setBusy(true);
    setFormError("");
    try {
      await patientsApi.startJourney(patientId, {
        pathway_id: pathwayId,
        ...(isClinician ? { priority } : {}),
        step_time_limits_hours: Object.fromEntries(
          Object.entries(timeLimits).map(([stepId, hours]) => [stepId, Number(hours)])
        ),
      });
      if (journeyOffset === 0) await journeys.refetch();
      else setJourneyOffset(0);
      setPathwayId("");
      setTimeLimits({});
      toast.success("Care journey started. The patient can now see it after signing in or refreshing their portal.");
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const savePriority = async (event, journey) => {
    event.preventDefault();
    if (prioritySavingId) return;
    const selected = priorityDrafts[journey.id] || journey.priority;
    if (selected === journey.priority) return;
    setPrioritySavingId(journey.id);
    try {
      await journeysApi.updatePriority(journey.id, selected);
      setPriorityDrafts(current => ({ ...current, [journey.id]: selected }));
      journeys.refetch().catch(() => {});
      toast.success("Journey priority updated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setPrioritySavingId(null);
    }
  };

  const doctorAssigned = () => {
    setDoctorAssignOpen(false);
    patient.refetch().catch(() => {});
    toast.success("Doctor assigned to this patient.");
  };

  if (patient.loading) return <DetailSkeleton />;
  if (patient.error) return <ErrorState error={patient.error} title="Could not load patient" />;

  return <div>
    <Link className="back-link" to="/patients"><ArrowLeft size={16} /> Back to patients</Link>
    <div className="patient-hero">
      <div className="person-avatar person-avatar--large">{initials(p.first_name, p.last_name)}</div>
      <div className="patient-identity">
        <span className="eyebrow">Patient profile</span>
        <h1>{p.first_name} {p.last_name}</h1>
        <div className="patient-meta">
          <span><code>{p.patient_reference}</code></span>
          <span><CalendarDays size={15} /> {formatDate(p.date_of_birth)}</span>
          <span><UserRound size={15} /> {p.gender}</span>
        </div>
      </div>
    </div>

    <div className="content-grid">
      <Panel wide title="Care journeys" subtitle="Pathways associated with this patient">
        {canStartJourney && !journeys.loading && !journeys.error && (hasActiveJourney ? <div className="start-journey-form start-journey-locked">
          <div className="start-journey-copy"><strong>Care journey in progress</strong><span>Start another journey after the current one is completed or cancelled.</span></div>
          <button className="primary-btn" type="button" disabled>Start journey</button>
        </div> : <form className="start-journey-form" onSubmit={startJourney}>
          <div className="start-journey-copy"><strong>Start a care journey</strong><span>Choose an active pathway to add its steps to this patient's portal.</span></div>
          {pathways.error ? <div className="event-form-error">Could not load pathways: {getErrorMessage(pathways.error)}</div> :
            pathwayRows.length ? <div className="start-journey-controls">
              <Select value={pathwayId} onChange={choosePathway} label="Care pathway" placeholder="Choose pathway" options={pathwayRows.map(w => ({ value: w.id, label: `${w.name} (v${w.version})` }))} disabled={busy} />
              {isClinician && <Select value={priority} onChange={setPriority} label="Priority" options={PRIORITIES.map(value => ({ value, label: humanize(value) }))} disabled={busy} />}
              <button className="primary-btn" type="submit" disabled={!pathwayId || busy}>{busy ? "Starting…" : "Start journey"}</button>
            </div> : <span className="start-journey-note">{pathways.loading ? "Loading pathways…" : "No active pathways are available."}</span>}
          {selectedPathway?.steps?.length > 0 && (
            <div className="journey-step-limits">
              <strong>Pathway schedule</strong>
              <p>Milestones are measured from the day this journey starts. Adjust the time allowed after each step becomes ready for this patient.</p>
              {selectedPathway.steps.map(step => (
                <div className="journey-step-limit" key={step.id}>
                  <span><b>{step.sequence_number}. {step.name}</b><small>{milestoneLabel(step.due_after_days)} · {step.due_after_days != null ? formatDate(new Date(Date.now() + step.due_after_days * 86400000)) : "Date to be confirmed"}</small></span>
                  <DurationInput label={`${step.name}: time allowed`} hours={timeLimits[step.id] ?? ""} onChange={value => setTimeLimits(current => ({ ...current, [step.id]: value }))} disabled={busy} />
                </div>
              ))}
            </div>
          )}
          {formError && <div className="event-form-error" role="alert">{formError}</div>}
        </form>)}
        {journeys.error ? <ErrorState error={journeys.error} title="Could not load journeys" /> : journeys.loading ? <SkeletonRows /> : js.length ? (
          <div className="journey-list">{js.map(j => (
            <div className="journey-card journey-card--open" key={j.id}
              onClick={event => {
                if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey &&
                    !event.target.closest("a, button, form, input, select, textarea, label")) navigate(`/journeys/${j.id}`);
              }}>
              <Link className="journey-card-open" to={`/journeys/${j.id}`}>
                <div className="journey-card-icon"><Network size={20} /></div>
                <div className="journey-card-main"><strong>{humanize(j.pathway_name || j.pathway_id || "Care pathway")}</strong><span>Started {formatDate(j.started_at)}</span></div>
              </Link>
              <Badge kind="status" value={j.status} />
              {isClinician && ACTIVE_JOURNEY_STATUSES.has(j.status) ? <form className="journey-priority-form" onSubmit={event => savePriority(event, j)}>
                <label>Priority<Select className="form-select" label={`Priority for ${j.pathway_name || "care journey"}`} value={priorityDrafts[j.id] || j.priority} disabled={prioritySavingId === j.id}
                  onChange={value => setPriorityDrafts(current => ({ ...current, [j.id]: value }))}
                  options={PRIORITIES.map(value => ({ value, label: humanize(value) }))} /></label>
                <button className="secondary-btn" type="submit" disabled={prioritySavingId === j.id || (priorityDrafts[j.id] || j.priority) === j.priority}>{prioritySavingId === j.id ? "Saving…" : "Save priority"}</button>
              </form> : <Badge kind="priority" value={j.priority} />}
              <Link className="journey-card-arrow" to={`/journeys/${j.id}`} aria-label={`Open ${j.pathway_name || "care journey"}`}><ChevronRight size={18} /></Link>
            </div>
          ))}</div>
        ) : <EmptyState icon={ClipboardList} title="No journeys found" text="This patient has no associated journeys." />}
        {!journeys.loading && !journeys.error && <Pagination offset={journeyOffset} count={js.length} total={journeys.data?.total ?? 0} onPage={setJourneyOffset} />}
      </Panel>

      <Panel title="Patient information" subtitle="Core demographic details">
        <div className="detail-list">
          <Detail label="Patient ID" value={p.id} />
          <Detail label="Reference" value={p.patient_reference} />
          <Detail label="Date of birth" value={formatDate(p.date_of_birth)} />
          <Detail label="Gender" value={p.gender} />
          <Detail label="Email" value={p.email} />
          <Detail label="Doctor" value={p.assigned_clinician_id ? <span className="patient-assignment"><span>{p.assigned_clinician_name || "Assigned doctor"}</span><span className="patient-assignment-tag">Assigned</span></span> : "Unassigned"} />
        </div>
        {isAdmin(user) && !p.assigned_clinician_id && <div className="patient-profile-assignment"><button className="primary-btn" type="button" onClick={() => setDoctorAssignOpen(true)}>Assign doctor</button></div>}
      </Panel>
    </div>
    {doctorAssignOpen && <DoctorAssignDrawer patient={p} onClose={closeDoctorAssign} onAssigned={doctorAssigned} />}
  </div>;
}
