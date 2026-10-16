import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { adminApi } from "../../../../services/index";
import { useAsync } from "../../../../hooks/useAsync";
import { getErrorMessage } from "../../../../utils/index";
import { Select } from "../../../../components/index";

export default function DoctorAssignDrawer({ patient, onClose, onAssigned }) {
  const [doctorId, setDoctorId] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { data: doctors, loading, error: doctorsError } = useAsync(() => adminApi.clinicians(), []);
  const busyRef = useRef(false);
  const closeButton = useRef(null);
  const returnFocus = useRef(document.activeElement);
  busyRef.current = busy;
  const matchingDoctors = (doctors || []).filter(doctor =>
    `${doctor.name} ${doctor.email}`.toLowerCase().includes(search.trim().toLowerCase())
  );

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    const onKeyDown = event => {
      if (event.key === "Escape" && !busyRef.current) onClose();
      if (event.key !== "Tab") return;
      const focusable = [...document.querySelectorAll(".doctor-assign-drawer button:not([disabled]), .doctor-assign-drawer input:not([disabled]):not([tabindex='-1']), .doctor-assign-drawer select:not([disabled])")];
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first) return;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocus.current?.focus();
    };
  }, [onClose]);

  const submit = async event => {
    event.preventDefault();
    if (!doctorId || busy) return;
    setBusy(true);
    setError("");
    try {
      await adminApi.assignPatient(doctorId, patient.id);
      onAssigned();
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="pathway-drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
      <aside className="pathway-drawer doctor-assign-drawer" role="dialog" aria-modal="true" aria-labelledby="doctor-assign-title">
        <div className="pathway-drawer-header">
          <div><span className="eyebrow">Patient assignment</span><h2 id="doctor-assign-title">Assign doctor</h2>
            <p>Choose the doctor who will care for {patient.first_name} {patient.last_name}.</p></div>
          <button ref={closeButton} className="icon-btn" type="button" aria-label="Close doctor assignment" onClick={onClose} disabled={busy}><X size={18} /></button>
        </div>
        <form className="pathway-form pathway-drawer-form" onSubmit={submit}>
          <div className="pathway-drawer-content">
            <label>Find a doctor<input type="search" value={search} onChange={event => { setSearch(event.target.value); setDoctorId(""); }} placeholder="Search by name or email" disabled={loading || busy} /></label>
            <label>Doctor<Select className="form-select" required label="Doctor" value={doctorId} onChange={setDoctorId} disabled={loading || busy} placeholder="Choose a doctor" options={[
              ...matchingDoctors.slice(0, 50).map(doctor => ({ value: String(doctor.id), label: `${doctor.name} (${doctor.email})` })),
            ]} /></label>
            {matchingDoctors.length > 50 && <p className="staff-create-hint">Showing 50 doctors. Search by name or email to narrow the list.</p>}
            {!loading && !doctorsError && (doctors || []).length > 0 && !matchingDoctors.length && <p className="staff-create-hint">No doctors match that search.</p>}
            <p className="staff-create-hint">Once assigned, this patient cannot be reassigned to another doctor.</p>
            {doctorsError && <div className="form-error" role="alert">Could not load doctors: {getErrorMessage(doctorsError)}</div>}
            {!loading && !doctorsError && !(doctors || []).length && <div className="form-error" role="alert">No active doctors are available.</div>}
            {error && <div className="form-error" role="alert">{error}</div>}
          </div>
          <div className="pathway-drawer-footer">
            <button className="secondary-btn" type="button" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="primary-btn" type="submit" disabled={busy || loading || !doctorId}>{busy ? "Assigning…" : "Assign doctor"}</button>
          </div>
        </form>
      </aside>
    </div>, document.body,
  );
}
