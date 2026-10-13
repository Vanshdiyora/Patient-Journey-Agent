import React, { useCallback, useState } from "react";
import { Plus, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { adminApi, patientsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { useTabs } from "../../hooks/useTabs";
import { formatDate, getErrorMessage, initials } from "../../utils";
import { isAdmin, isCoordinator, portalName } from "../../utils/roles";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { PageHeading, Panel, EmptyState, ErrorState, Pagination, SearchBox, SkeletonRows, TabBar } from "../../components";
import { TABS_BY_ROLE } from "./tabs";
import PatientCreateDrawer from "./PatientCreateDrawer";
import DoctorAssignDrawer from "./DoctorAssignDrawer";

export default function Patients() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const tabs = TABS_BY_ROLE[String(user?.role || "").toUpperCase()] || TABS_BY_ROLE.ADMIN;
  const { active: tab, select: setTab } = useTabs("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [credentials, setCredentials] = useState(null);
  const [doctorAssignPatient, setDoctorAssignPatient] = useState(null);
  const [claimingId, setClaimingId] = useState(null);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);
  const closeDoctorAssign = useCallback(() => setDoctorAssignPatient(null), []);
  const toast = useToast();
  const isClinician = String(user?.role || "").toUpperCase() === "CLINICIAN";
  const limit = 10;
  const { data: clinicians, error: cliniciansError } = useAsync(
    () => isAdmin(user) ? adminApi.clinicians() : Promise.resolve([]), [user?.role]
  );
  const { data, loading, error } = useAsync(
    () => patientsApi.list({ search: search || undefined, filter: tab || undefined, limit, offset }),
    [search, offset, tab, refresh]
  );
  const patients = Array.isArray(data) ? data : data?.items || data?.patients || [];
  const activeTab = tabs.find(t => t.id === tab) || tabs[0];

  const patientCreated = created => {
    setCredentials(created);
    setDrawerOpen(false);
    setOffset(0);
    setRefresh(value => value + 1);
  };

  const doctorAssigned = () => {
    setDoctorAssignPatient(null);
    setRefresh(value => value + 1);
    toast.success("Doctor assigned to this patient.");
  };

  const claimPatient = async patientId => {
    if (claimingId) return;
    setClaimingId(patientId);
    try {
      await patientsApi.claim(patientId);
      toast.success("Patient assigned to you. You can now open their profile.");
    } catch (cause) {
      toast.error(getErrorMessage(cause));
    } finally {
      setRefresh(value => value + 1);
      setClaimingId(null);
    }
  };

  return <div>
    <PageHeading eyebrow={portalName(user)} title={isCoordinator(user) ? "Patient follow-ups" : "Patients"}
      description={isAdmin(user) ? "View patients and their assigned clinicians." : isCoordinator(user) ? "Patients needing coordination follow-up." : "Browse patients, claim an unassigned patient, and follow those in your care."}
      actions={isAdmin(user) && <button className="primary-btn" type="button" onClick={() => setDrawerOpen(true)}><Plus size={16} /> Create patient</button>} />
    {drawerOpen && <PatientCreateDrawer clinicians={clinicians} cliniciansError={cliniciansError} onClose={closeDrawer} onCreated={patientCreated} />}
    {doctorAssignPatient && <DoctorAssignDrawer patient={doctorAssignPatient} onClose={closeDoctorAssign} onAssigned={doctorAssigned} />}
    {credentials && <div className="credential-overlay" role="dialog" aria-modal="true" aria-label="Patient sign-in details">
      <div className="credential-card">
        <h2>Patient account created</h2>
        <p>Copy these details now and share them with the patient. The temporary password will not be shown again.</p>
        <div className="detail-list">
          <div className="detail-row"><span>Patient ID</span><strong>{credentials.patient_reference}</strong></div>
          <div className="detail-row"><span>Email</span><strong>{credentials.email}</strong></div>
          <div className="detail-row"><span>Temporary password</span><strong>{credentials.temporary_password}</strong></div>
        </div>
        <button className="primary-btn" type="button" onClick={() => setCredentials(null)}>I have saved these details</button>
      </div>
    </div>}
    <Panel>
      <TabBar tabs={tabs} active={tab} onChange={(id) => { setTab(id); setOffset(0); }} className="tab-bar--inset" />
      <div className="toolbar" style={{ borderTop: "1px solid var(--line)" }}>
        <SearchBox value={search} onChange={v => { setSearch(v); setOffset(0); }} placeholder="Search by name or patient reference…" />
        <span className="result-count">{activeTab?.label}</span>
      </div>
      {error ? <ErrorState error={error} title="Could not load patients" /> : loading ? <SkeletonRows /> : patients.length ? (
        <div className="table-wrap"><table>
          <thead><tr><th>Patient</th><th>Reference</th><th>Date of birth</th><th>Doctor</th><th>{isClinician || isAdmin(user) ? "Action" : "Profile"}</th></tr></thead>
          <tbody>{patients.map(p => {
            const canOpenProfile = !isClinician || p.assigned_clinician_id === user?.id;
            const profilePath = `/patients/${p.id}`;
            return (
            <tr key={p.id} className={canOpenProfile ? "patient-row--open" : undefined}
              onClick={canOpenProfile ? event => {
                if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey &&
                    !event.target.closest("a, button, input, select, textarea")) navigate(profilePath);
              } : undefined}>
              <td><div className="person-cell"><div className="person-avatar">{initials(p.first_name, p.last_name)}</div><div>{canOpenProfile ? <Link className="table-primary" to={profilePath}>{p.first_name} {p.last_name}</Link> : <strong className="table-primary">{p.first_name} {p.last_name}</strong>}<span>Patient record</span></div></div></td>
              <td><code>{p.patient_reference}</code></td>
              <td>{formatDate(p.date_of_birth)}</td>
              <td>{p.assigned_clinician_id ? <div className="patient-assignment"><span>{p.assigned_clinician_name || "Assigned doctor"}</span><span className="patient-assignment-tag">Assigned</span></div> : <span className="patient-unassigned">Unassigned</span>}</td>
              <td>{canOpenProfile ? <div className="patient-row-actions"><Link className="table-link" to={profilePath}>Open profile</Link>{isAdmin(user) && !p.assigned_clinician_id && <button className="secondary-btn patient-claim-btn" type="button" onClick={() => setDoctorAssignPatient(p)}>Assign doctor</button>}</div> : isClinician && !p.assigned_clinician_id ? <button className="secondary-btn patient-claim-btn" type="button" disabled={Boolean(claimingId)} onClick={() => claimPatient(p.id)}>{claimingId === p.id ? "Assigning…" : "Assign to me"}</button> : <span className="patient-assignment-muted">Assigned to another doctor</span>}</td>
            </tr>
          ); })}</tbody>
        </table></div>
      ) : <EmptyState icon={Users} title="No patients here" text={`No patients match "${activeTab?.label}". Try another tab or clear the search.`} />}
      {!loading && !error && <Pagination offset={offset} limit={limit} count={patients.length} total={data?.total ?? patients.length} onPage={setOffset} />}
    </Panel>
  </div>;
}
