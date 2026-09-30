import React from "react";
import { ArrowLeft, CalendarDays, ChevronRight, ClipboardList, Network, UserRound } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { patientsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, initials, humanize, toList } from "../../utils";
import { Panel, EmptyState, ErrorState, Badge, DetailSkeleton } from "../../components";

function Detail({ label, value }) {
  return <div className="detail-row"><span>{label}</span><strong>{value || "—"}</strong></div>;
}

export default function PatientDetail() {
  const { patientId } = useParams();
  const patient = useAsync(() => patientsApi.get(patientId), [patientId]);
  const journeys = useAsync(() => patientsApi.journeys(patientId), [patientId]);
  const p = patient.data;
  const js = toList(journeys.data, "items");

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
        {js.length ? (
          <div className="journey-list">{js.map(j => (
            <Link className="journey-card" key={j.id} to={`/journeys/${j.id}`}>
              <div className="journey-card-icon"><Network size={20} /></div>
              <div className="journey-card-main"><strong>{humanize(j.pathway_name || j.pathway_id || "Care pathway")}</strong><span>Started {formatDate(j.started_at)}</span></div>
              <Badge kind="status" value={j.status} />
              <ChevronRight size={18} />
            </Link>
          ))}</div>
        ) : <EmptyState icon={ClipboardList} title="No journeys found" text="This patient has no associated journeys." />}
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
