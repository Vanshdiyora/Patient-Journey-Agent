import React, { useEffect, useState } from "react";
import { ArrowLeft, CalendarDays, ChevronRight, ClipboardList, Network, UserRound } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { journeysApi, patientsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, getErrorMessage, initials, humanize, toList } from "../../utils";
import { Panel, EmptyState, ErrorState, Badge, DetailSkeleton, Select, Pagination, SkeletonRows } from "../../components";
import { useToast } from "../../context/ToastContext";

function Detail({ label, value }) {
  return <div className="detail-row"><span>{label}</span><strong>{value || "—"}</strong></div>;
}

export default function PatientDetail() {
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
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const p = patient.data;
  const js = toList(journeys.data, "items");
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
    if (!pathwayId || busy) return;
    setBusy(true);
    setFormError("");
    try {
      await patientsApi.startJourney(patientId, {
        pathway_id: pathwayId,
        priority,
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
        <form className="start-journey-form" onSubmit={startJourney}>
          <div className="start-journey-copy"><strong>Start a care journey</strong><span>Choose an active pathway to add its steps to this patient's portal.</span></div>
          {pathways.error ? <div className="event-form-error">Could not load pathways: {getErrorMessage(pathways.error)}</div> :
            pathwayRows.length ? <div className="start-journey-controls">
              <Select value={pathwayId} onChange={choosePathway} label="Care pathway" placeholder="Choose pathway" options={pathwayRows.map(w => ({ value: w.id, label: `${w.name} (v${w.version})` }))} disabled={busy} />
              <Select value={priority} onChange={setPriority} label="Priority" options={["LOW", "MEDIUM", "HIGH", "CRITICAL"].map(value => ({ value, label: humanize(value) }))} disabled={busy} />
              <button className="primary-btn" type="submit" disabled={!pathwayId || busy}>{busy ? "Starting…" : "Start journey"}</button>
            </div> : <span className="start-journey-note">{pathways.loading ? "Loading pathways…" : "No active pathways are available."}</span>}
          {selectedPathway?.steps?.length > 0 && (
            <div className="journey-step-limits">
              <strong>Step time limits</strong>
              <p>Set the allowed time from when each step becomes ready. These values apply to this patient’s journey only.</p>
              {selectedPathway.steps.map(step => (
                <label className="journey-step-limit" key={step.id}>
                  <span><b>{step.sequence_number}. {step.name}</b><small>{step.description || step.code}</small></span>
                  <span className="journey-step-limit-input">
                    <input
                      aria-label={`${step.name} time limit in hours`}
                      type="number"
                      min="1"
                      max="8760"
                      required
                      value={timeLimits[step.id] ?? ""}
                      onChange={event => setTimeLimits(current => ({ ...current, [step.id]: event.target.value }))}
                      disabled={busy}
                    />
                    <small>hours</small>
                  </span>
                </label>
              ))}
            </div>
          )}
          {formError && <div className="event-form-error" role="alert">{formError}</div>}
        </form>
        {journeys.error ? <ErrorState error={journeys.error} title="Could not load journeys" /> : journeys.loading ? <SkeletonRows /> : js.length ? (
          <div className="journey-list">{js.map(j => (
            <Link className="journey-card" key={j.id} to={`/journeys/${j.id}`}>
              <div className="journey-card-icon"><Network size={20} /></div>
              <div className="journey-card-main"><strong>{humanize(j.pathway_name || j.pathway_id || "Care pathway")}</strong><span>Started {formatDate(j.started_at)}</span></div>
              <Badge kind="status" value={j.status} />
              <ChevronRight size={18} />
            </Link>
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
        </div>
      </Panel>
    </div>
  </div>;
}
