import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { adminApi } from "../services";
import { getErrorMessage, humanize } from "../utils";
import { ROLES } from "../utils/roles";
import { Select } from "../components";

const emptyForm = { display_name: "", email: "", password: "", role: ROLES.CLINICIAN };
const staffRoles = [ROLES.CLINICIAN, ROLES.CARE_COORDINATOR, ROLES.ADMIN];

export default function StaffCreateDrawer({ onClose, onCreated }) {
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const busyRef = useRef(false);
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
      const focusable = [...document.querySelectorAll(".staff-create-drawer button:not([disabled]), .staff-create-drawer input:not([disabled]):not([tabindex='-1']), .staff-create-drawer select:not([disabled])")];
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
      const created = await adminApi.createStaff(form);
      onCreated(created);
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="pathway-drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
      <aside className="pathway-drawer staff-create-drawer" role="dialog" aria-modal="true" aria-labelledby="staff-create-title">
        <div className="pathway-drawer-header">
          <div><span className="eyebrow">Administration</span><h2 id="staff-create-title">Create staff account</h2>
            <p>Enter account details and choose the staff member's role.</p></div>
          <button ref={closeButton} className="icon-btn" type="button" aria-label="Close staff form" onClick={onClose} disabled={busy}><X size={18} /></button>
        </div>
        <form className="pathway-form pathway-drawer-form" onSubmit={submit}>
          <div className="pathway-drawer-content">
            <div className="pathway-form-grid staff-create-grid">
              <label>Full name<input required maxLength={200} autoComplete="name" value={form.display_name} onChange={event => set("display_name", event.target.value)} placeholder="Doctor or staff name" /></label>
              <label>Work email<input required type="email" autoComplete="email" value={form.email} onChange={event => set("email", event.target.value)} placeholder="name@clinic.example" /></label>
              <label>Initial password<input required type="password" minLength={8} maxLength={128} autoComplete="new-password" value={form.password} onChange={event => set("password", event.target.value)} placeholder="At least 8 characters" /></label>
              <label>Staff role<Select className="form-select" required label="Staff role" value={form.role} onChange={value => set("role", value)}
                options={staffRoles.map(role => ({ value: role, label: humanize(role) }))} /></label>
            </div>
            <p className="staff-create-hint">Share the initial password securely with the staff member. They can change it after signing in.</p>
            {error && <div className="form-error" role="alert">{error}</div>}
          </div>
          <div className="pathway-drawer-footer">
            <button className="secondary-btn" type="button" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="primary-btn" type="submit" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
          </div>
        </form>
      </aside>
    </div>, document.body,
  );
}
