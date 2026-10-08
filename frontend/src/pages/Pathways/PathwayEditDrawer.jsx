import React, { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Plus, Trash2, X } from "lucide-react";
import { createPortal } from "react-dom";
import { Select } from "../../components";
import { useToast } from "../../context/ToastContext";
import { pathwaysApi } from "../../services";
import { getErrorMessage, humanize } from "../../utils";

const OWNER_ROLES = ["PATIENT", "CLINICIAN", "CARE_COORDINATOR", "ADMIN", "STAFF", "AGENT"];
const OWNER_OPTIONS = OWNER_ROLES.map(role => ({ value: role, label: humanize(role) }));

const fromPathway = pathway => ({
  name: pathway.name,
  description: pathway.description || "",
  steps: (pathway.steps || []).map(step => ({
    ...step,
    key: step.id,
    description: step.description || "",
    owner_role: step.owner_role || "STAFF",
  })),
});

export default function PathwayEditDrawer({ pathway, onClose, onSaved }) {
  const [form, setForm] = useState(() => fromPathway(pathway));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const initial = useRef(JSON.stringify(fromPathway(pathway)));
  const closeButton = useRef(null);
  const returnFocus = useRef(document.activeElement);
  const toast = useToast();

  const dirty = JSON.stringify(form) !== initial.current;
  const close = () => {
    if (busy) return;
    if (dirty && !window.confirm("Discard your pathway changes?")) return;
    onClose();
  };

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    return () => {
      document.body.style.overflow = previous;
      returnFocus.current?.focus();
    };
  }, []);

  useEffect(() => {
    const onKeyDown = event => {
      if (event.key === "Escape" && !document.querySelector(".select-list")) close();
      if (event.key !== "Tab") return;
      const focusable = [...document.querySelectorAll(".pathway-drawer button:not([disabled]), .pathway-drawer input:not([disabled]), .pathway-drawer textarea:not([disabled])")];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  });

  const updateStep = (index, key, value) => setForm(current => ({
    ...current,
    steps: current.steps.map((step, i) => i === index ? { ...step, [key]: value } : step),
  }));

  const addStep = () => setForm(current => {
    const codes = new Set(current.steps.map(step => step.code));
    let number = current.steps.length + 1;
    while (codes.has(`STEP-${number}`)) number += 1;
    return {
      ...current,
      steps: [...current.steps, {
        key: crypto.randomUUID(), code: `STEP-${number}`, name: "", description: "",
        step_type: "FOLLOWUP", owner_role: "CARE_COORDINATOR",
        required: true, time_limit_hours: 24,
      }],
    };
  });

  const moveStep = (index, direction) => setForm(current => {
    const steps = [...current.steps];
    [steps[index], steps[index + direction]] = [steps[index + direction], steps[index]];
    return { ...current, steps };
  });

  const submit = async event => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await pathwaysApi.update(pathway.id, {
        name: form.name.trim(),
        description: form.description.trim() || null,
        steps: form.steps.map(step => ({
          id: step.id || null,
          code: step.code.trim(),
          name: step.name.trim(),
          description: step.description.trim() || null,
          step_type: step.step_type.trim(),
          owner_role: step.owner_role,
          required: step.required,
          time_limit_hours: Number(step.time_limit_hours),
          completion_criteria: step.completion_criteria || null,
        })),
      });
      await onSaved();
      toast.success("Care pathway updated. Active journeys will sync when their steps are next loaded.");
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="pathway-drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
      <aside className="pathway-drawer" role="dialog" aria-modal="true" aria-labelledby="pathway-drawer-title">
        <div className="pathway-drawer-header">
          <div>
            <span className="eyebrow">Care pathway · {pathway.code} · v{pathway.version}</span>
            <h2 id="pathway-drawer-title">Edit pathway</h2>
            <p>Saving creates a new version. Active patient journeys sync to it when their steps are next loaded; completed journeys stay on their original version.</p>
          </div>
          <button ref={closeButton} className="icon-btn" type="button" aria-label="Close edit pathway" onClick={close} disabled={busy}><X size={18} /></button>
        </div>
        <form className="pathway-form pathway-drawer-form" onSubmit={submit}>
          <div className="pathway-drawer-content">
            <div className="pathway-form-grid pathway-drawer-grid">
              <label>Pathway code
                <input value={pathway.code} readOnly aria-describedby="pathway-code-help" />
                <small id="pathway-code-help">Code identifies this pathway across versions.</small>
              </label>
              <label>Pathway name
                <input required maxLength="200" value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} />
              </label>
              <label className="pathway-description-field">Description
                <textarea rows="2" maxLength="2000" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} />
              </label>
            </div>
            <div className="pathway-steps-heading">
              <div><strong>Pathway steps</strong><span>Arrange steps in the order patients will follow them.</span></div>
              <button className="secondary-btn" type="button" onClick={addStep} disabled={busy || form.steps.length >= 100}><Plus size={15} /> Add step</button>
            </div>
            <div className="pathway-step-editors">
              {form.steps.map((step, index) => (
                <section className="pathway-step-editor" key={step.key}>
                  <div className="pathway-step-editor-heading">
                    <strong>Step {index + 1}</strong>
                    <div className="pathway-step-actions">
                      <button className="icon-btn" type="button" aria-label={`Move step ${index + 1} up`} disabled={busy || index === 0} onClick={() => moveStep(index, -1)}><ArrowUp size={15} /></button>
                      <button className="icon-btn" type="button" aria-label={`Move step ${index + 1} down`} disabled={busy || index === form.steps.length - 1} onClick={() => moveStep(index, 1)}><ArrowDown size={15} /></button>
                      <button className="icon-btn" type="button" aria-label={`Remove step ${index + 1}`} disabled={busy || form.steps.length === 1} onClick={() => setForm(current => ({ ...current, steps: current.steps.filter((_, i) => i !== index) }))}><Trash2 size={15} /></button>
                    </div>
                  </div>
                  <div className="pathway-form-grid pathway-drawer-grid">
                    <label>Step code<input required maxLength="100" value={step.code} onChange={event => updateStep(index, "code", event.target.value)} /></label>
                    <label>Step name<input required maxLength="200" value={step.name} onChange={event => updateStep(index, "name", event.target.value)} /></label>
                    <label>Step type<input required maxLength="50" value={step.step_type} onChange={event => updateStep(index, "step_type", event.target.value)} /></label>
                    <div className="pathway-owner-field"><span>Responsible role</span><Select label={`Responsible role for step ${index + 1}`} value={step.owner_role} onChange={value => updateStep(index, "owner_role", value)} options={OWNER_OPTIONS} className="pathway-owner-select" /></div>
                    <label>Time limit (hours)<input required type="number" min="1" max="8760" value={step.time_limit_hours} onChange={event => updateStep(index, "time_limit_hours", event.target.value)} /></label>
                    <label className="pathway-required-field"><input type="checkbox" checked={step.required} onChange={event => updateStep(index, "required", event.target.checked)} /> Required step</label>
                    <label className="pathway-description-field">Step details<textarea rows="2" maxLength="2000" value={step.description} onChange={event => updateStep(index, "description", event.target.value)} /></label>
                  </div>
                </section>
              ))}
            </div>
            {error && <div className="form-error" role="alert">{error}</div>}
          </div>
          <div className="pathway-drawer-footer">
            <button className="secondary-btn" type="button" onClick={close} disabled={busy}>Cancel</button>
            <button className="primary-btn" type="submit" disabled={busy || !dirty}>{busy ? "Saving…" : "Save new version"}</button>
          </div>
        </form>
      </aside>
    </div>,
    document.body,
  );
}
