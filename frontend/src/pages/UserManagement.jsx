import React, { useState } from "react";
import { ShieldCheck, UserCog } from "lucide-react";
import { adminApi, patientsApi } from "../services";
import { useAsync } from "../hooks/useAsync";
import { getErrorMessage, humanize, toList } from "../utils";
import { useConfirm } from "../components/ConfirmModal";
import { useToast } from "../context/ToastContext";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, SkeletonRows, AlertBanner, Select, Pagination } from "../components";
import { ROLES } from "../utils/roles";

export default function UserManagement() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [offset, setOffset] = useState(0);
  const { data, loading, error } = useAsync(() => adminApi.users({ limit: 10, offset }), [refreshKey, offset]);
  const users = toList(data, "items", "users");
  const [saving, setSaving] = useState("");
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [patientSearch, setPatientSearch] = useState("");
  const [staffForm, setStaffForm] = useState({ email: "", display_name: "", password: "", role: ROLES.CLINICIAN });
  const [assignmentRefresh, setAssignmentRefresh] = useState(0);
  const { data: assignments, loading: assignmentsLoading } = useAsync(
    () => selectedStaff ? adminApi.patientAssignments(selectedStaff.id) : Promise.resolve({ patient_ids: [] }),
    [selectedStaff?.id, assignmentRefresh],
  );
  const { data: matchingPatients } = useAsync(
    () => patientSearch.trim() ? patientsApi.list({ search: patientSearch.trim(), limit: 10 }) : Promise.resolve({ items: [] }),
    [patientSearch],
  );
  const [feedback, setFeedback] = useState(null);
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();

  const setRole = async (u, role) => {
    if (role === u.role) return;
    const ok = await confirm({
      title: `Change role to ${humanize(role)}?`,
      message: `${u.display_name || u.email} will immediately gain the permissions of the ${humanize(role)} role.`,
      confirmLabel: "Change role",
      intent: "primary",
    });
    if (!ok) {
      setRefreshKey(k => k + 1); // revert the Select to the stored role
      return;
    }
    await applyRole(u, role);
  };

  const applyRole = async (u, role) => {
    setSaving(u.id);
    try {
      await adminApi.setUserRole(u.id, { role });
      toast.success(`${u.display_name || u.email} is now ${humanize(role)}.`);
      setRefreshKey(k => k + 1);
    } catch (err) {
      toast.error(getErrorMessage(err));
      setRefreshKey(k => k + 1);
    } setSaving("");
  };

  const toggleActive = async (u) => {
    const ok = await confirm({
      title: u.is_active ? "Deactivate this account?" : "Reactivate this account?",
      message: u.is_active
        ? `${u.display_name || u.email} will immediately lose access to the workspace.`
        : `${u.display_name || u.email} will regain access to the workspace.`,
      confirmLabel: u.is_active ? "Deactivate" : "Reactivate",
      intent: u.is_active ? "danger" : "primary",
    });
    if (!ok) return;
    setSaving(u.id);
    try {
      await adminApi.setUserActive(u.id, { is_active: !u.is_active });
      toast.success(`${u.display_name || u.email} ${u.is_active ? "deactivated" : "reactivated"}.`);
      setRefreshKey(k => k + 1);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } setSaving("");
  };

  const createStaff = async (event) => {
    event.preventDefault();
    setSaving("create");
    try {
      await adminApi.createStaff(staffForm);
      setStaffForm({ email: "", display_name: "", password: "", role: ROLES.CLINICIAN });
      setRefreshKey(k => k + 1);
      toast.success("Staff account created.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving("");
    }
  };

  const changeAssignment = async (patientId, assign) => {
    const staff = selectedStaff;
    if (!staff) return;
    if (!assign) {
      const ok = await confirm({
        title: "Remove patient access?",
        message: `${staff.display_name || staff.email} will immediately lose access to this patient and their journeys.`,
        confirmLabel: "Remove access",
        intent: "danger",
      });
      if (!ok) return;
    }
    setSaving(patientId);
    try {
      if (assign) await adminApi.assignPatient(staff.id, patientId);
      else await adminApi.unassignPatient(staff.id, patientId);
      setAssignmentRefresh(k => k + 1);
      toast.success(assign ? "Patient access granted." : "Patient access removed.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving("");
    }
  };

  return <div>
    <PageHeading
      eyebrow="Administration"
      title="User management"
      description="Manage application identities, roles and activation status."
    />
    <Panel title="Application users" subtitle={`${data?.total ?? users.length} registered identities`} headerIcon={UserCog}>
      {feedback && <div style={{ padding: "0 18px" }}><AlertBanner tone={feedback.tone}>{feedback.text}</AlertBanner></div>}
      {error ? <ErrorState error={error} title="Could not load users" /> :
        loading ? <SkeletonRows /> :
          users.length ? (
            <div className="table-wrap"><table>
              <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>{users.map(u => (
                <tr key={u.id}>
                  <td><div className="person-cell">
                    <div className="person-avatar">{(u.display_name || u.email)[0].toUpperCase()}</div>
                    <div><span className="table-primary">{u.display_name || u.email}</span><span>{u.email}</span></div>
                  </div></td>
                  <td>
                    <Select
                      value={u.role}
                      disabled={saving === u.id || u.role === ROLES.PATIENT}
                      onChange={v => setRole(u, v)}
                      options={(u.role === ROLES.PATIENT ? [ROLES.PATIENT] : [ROLES.ADMIN, ROLES.CLINICIAN, ROLES.CARE_COORDINATOR]).map(r => ({ value: r, label: humanize(r) }))}
                      className="role-select"
                    />
                  </td>
                  <td><Badge kind="status" value={u.is_active ? "active" : "cancelled"} fallback={u.is_active ? "Active" : "Inactive"} /></td>
                  <td>
                    {(u.role === ROLES.CLINICIAN || u.role === ROLES.CARE_COORDINATOR) && (
                      <button className="secondary-btn" onClick={() => setSelectedStaff(u)}>Patient access</button>
                    )}
                    <button className="secondary-btn" disabled={saving === u.id} onClick={() => toggleActive(u)}>
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <EmptyState icon={ShieldCheck} title="No users" text="No identities are registered yet." />}
      {!loading && !error && <Pagination offset={offset} count={users.length} total={data?.total ?? 0} onPage={setOffset} />}
    </Panel>
    <Panel title="Create staff account" subtitle="Only administrators can provision staff identities.">
      <form onSubmit={createStaff} className="form-stack" style={{ padding: 18 }}>
        <label>Name<input required maxLength={200} value={staffForm.display_name} onChange={e => setStaffForm(f => ({ ...f, display_name: e.target.value }))} /></label>
        <label>Email<input required type="email" value={staffForm.email} onChange={e => setStaffForm(f => ({ ...f, email: e.target.value }))} /></label>
        <label>Initial password<input required type="password" minLength={8} maxLength={128} value={staffForm.password} onChange={e => setStaffForm(f => ({ ...f, password: e.target.value }))} /></label>
        <label>Role<Select value={staffForm.role} onChange={role => setStaffForm(f => ({ ...f, role }))}
          options={[ROLES.CLINICIAN, ROLES.CARE_COORDINATOR, ROLES.ADMIN].map(role => ({ value: role, label: humanize(role) }))} /></label>
        <button className="primary-btn" type="submit" disabled={saving === "create"}>Create account</button>
      </form>
    </Panel>
    {selectedStaff && <Panel title={`Patient access: ${selectedStaff.display_name || selectedStaff.email}`} subtitle="Clinical and coordination staff can see only assigned patients.">
      <div style={{ padding: 18 }}>
        <button className="secondary-btn" onClick={() => setSelectedStaff(null)}>Close</button>
        <p>Assigned patients</p>
        {assignmentsLoading ? <SkeletonRows /> : (assignments?.patients || []).length ? (
          <ul>{assignments.patients.map(patient => <li key={patient.id}>{patient.name} ({patient.reference}) <button className="secondary-btn" disabled={saving === patient.id} onClick={() => changeAssignment(patient.id, false)}>Remove access</button></li>)}</ul>
        ) : <p>No patients assigned.</p>}
        <label>Find a patient to assign<input value={patientSearch} onChange={e => setPatientSearch(e.target.value)} placeholder="Search name or reference" /></label>
        {patientSearch.trim() && <ul>{toList(matchingPatients, "items", "patients").map(patient => (
          <li key={patient.id}>{patient.first_name} {patient.last_name} ({patient.patient_reference}){" "}
            <button className="secondary-btn" disabled={saving === patient.id || (assignments?.patient_ids || []).includes(patient.id)} onClick={() => changeAssignment(patient.id, true)}>
              {(assignments?.patient_ids || []).includes(patient.id) ? "Assigned" : "Grant access"}
            </button>
          </li>
        ))}</ul>}
      </div>
    </Panel>}
    {confirmModal}
  </div>;
}
