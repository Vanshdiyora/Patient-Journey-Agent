import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { adminApi } from "../../services";
import { getErrorMessage } from "../../utils";
import { Select } from "../../components";

const emptyForm = { first_name: "", last_name: "", email: "", date_of_birth: "", gender: "", clinician_id: "" };

export default function PatientCreateDrawer({ clinicians, cliniciansError, onClose, onCreated }) {
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState("");
  const closeButton = useRef(null);
  const returnFocus = useRef(document.activeElement);
  busyRef.current = busy;
  const set = (field, value) => setForm(current => ({ ...current, [field]: value }));

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    const onKeyDown = event => {
      if (event.key === "Escape" && !busyRef.current) onClose();
      if (event.key !== "Tab") return;
      const focusable = [...document.querySelectorAll(".patient-create-drawer button:not([disabled]), .patient-create-drawer input:not([disabled]):not([tabindex='-1']), .patient-create-drawer select:not([disabled])")];
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
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await adminApi.createPatient({ ...form, clinician_id: form.clinician_id || null });
      onCreated(created);
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="pathway-drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
      <aside className="pathway-drawer patient-create-drawer" role="dialog" aria-modal="true" aria-labelledby="patient-create-title">
        <div className="pathway-drawer-header">
          <div><span className="eyebrow">Administration</span><h2 id="patient-create-title">Create patient account</h2>
            <p>Enter patient details. You can assign a doctor now or later.</p></div>
          <button ref={closeButton} className="icon-btn" type="button" aria-label="Close patient form" onClick={onClose} disabled={busy}><X size={18} /></button>
        </div>
        <form className="pathway-form pathway-drawer-form" onSubmit={submit}>
          <div className="pathway-drawer-content">
            <div className="pathway-form-grid pathway-drawer-grid">
              <label>First name<input required maxLength={80} autoComplete="given-name" value={form.first_name} onChange={event => set("first_name", event.target.value)} /></label>
              <label>Last name<input required maxLength={80} autoComplete="family-name" value={form.last_name} onChange={event => set("last_name", event.target.value)} /></label>
              <label className="patient-drawer-full">Patient email<input required type="email" autoComplete="email" value={form.email} onChange={event => set("email", event.target.value)} /></label>
              <label>Date of birth<input required type="date" max={new Date().toISOString().slice(0, 10)} value={form.date_of_birth} onChange={event => set("date_of_birth", event.target.value)} /></label>
              <label>Gender<Select className="form-select" required label="Gender" value={form.gender} onChange={value => set("gender", value)} placeholder="Select gender" options={[
                { value: "Female", label: "Female" },
                { value: "Male", label: "Male" },
                { value: "Non-binary", label: "Non-binary" },
                { value: "Other", label: "Other" },
                { value: "Prefer not to say", label: "Prefer not to say" },
              ]} /></label>
              <label className="patient-drawer-full">Assign clinician (optional)<Select className="form-select" label="Assign clinician (optional)" value={form.clinician_id} onChange={value => set("clinician_id", value)} placeholder="Assign later" options={[
                { value: "", label: "Assign later" },
                ...(clinicians || []).map(clinician => ({ value: String(clinician.id), label: `${clinician.name} (${clinician.email})` })),
              ]} /></label>
            </div>
            {cliniciansError && <div className="form-error" role="alert">Could not load clinicians: {getErrorMessage(cliniciansError)}</div>}
            {error && <div className="form-error" role="alert">{error}</div>}
          </div>
          <div className="pathway-drawer-footer">
            <button className="secondary-btn" type="button" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="primary-btn" type="submit" disabled={busy}>{busy ? "Creating…" : "Create patient"}</button>
          </div>
        </form>
      </aside>
    </div>, document.body,
  );
}
