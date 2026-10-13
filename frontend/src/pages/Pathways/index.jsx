import React, { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { pathwaysApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { getErrorMessage, humanize, toList } from "../../utils";
import { PageHeading, Panel, ErrorState, EmptyState, Badge, Select, Pagination } from "../../components";
import { useToast } from "../../context/ToastContext";
import PathwayEditDrawer from "./PathwayEditDrawer";
import DurationInput from "../../components/DurationInput";
import { formatDurationHours, milestoneLabel } from "../../utils/duration";

const newStep = (index) => ({
  key: crypto.randomUUID(),
  code: `STEP-${index + 1}`,
  name: "",
  description: "",
  step_type: "FOLLOWUP",
  owner_role: "CARE_COORDINATOR",
  time_limit_hours: 24,
  due_after_days: index + 1,
});

const OWNER_ROLES = ["PATIENT", "CLINICIAN", "CARE_COORDINATOR", "ADMIN", "AGENT"];
const OWNER_ROLE_OPTIONS = OWNER_ROLES.map(role => ({ value: role, label: humanize(role) }));

export default function Pathways() {
  const [offset, setOffset] = useState(0);
  const pathways = useAsync(() => pathwaysApi.list({ latest_only: true, limit: 10, offset }), [offset]);
  const toast = useToast();
  const [form, setForm] = useState({
    code: "",
    name: "",
    description: "",
    steps: [newStep(0)],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null);
  const rows = toList(pathways.data, "items");

  const updateStep = (index, key, value) => {
    setForm(current => ({
      ...current,
      steps: current.steps.map((step, i) => i === index ? { ...step, [key]: value } : step),
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await pathwaysApi.create({
        code: form.code.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
        steps: form.steps.map((step, index) => ({
          code: step.code.trim(),
          name: step.name.trim(),
          description: step.description.trim() || null,
          step_type: step.step_type.trim(),
          owner_role: step.owner_role,
          sequence_number: index + 1,
          time_limit_hours: Number(step.time_limit_hours),
          due_after_days: Number(step.due_after_days),
        })),
      });
      setForm({ code: "", name: "", description: "", steps: [newStep(0)] });
      await pathways.refetch();
      toast.success("Care pathway created and activated.");
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  };

  return <div>
    <PageHeading
      eyebrow="Administrator tools"
      title="Care pathways"
      description="Create reusable pathways with milestone days and a clear time allowance for each step."
    />

    <Panel wide title="Create a pathway" subtitle="New pathways become active and can be assigned to patients immediately.">
      <form className="pathway-form" onSubmit={submit}>
        <div className="pathway-form-grid">
          <label>Pathway code
            <input required maxLength="100" value={form.code} onChange={event => setForm(current => ({ ...current, code: event.target.value }))} placeholder="POST-DISCHARGE" />
          </label>
          <label>Pathway name
            <input required maxLength="200" value={form.name} onChange={event => setForm(current => ({ ...current, name: event.target.value }))} placeholder="Post-discharge follow-up" />
          </label>
          <label className="pathway-description-field">Description
            <textarea maxLength="2000" rows="2" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} placeholder="Describe the purpose of this pathway" />
          </label>
        </div>

        <div className="pathway-steps-heading">
          <div><strong>Pathway steps</strong><span>Set when each milestone is expected and how long a ready step may take.</span></div>
          <button
            className="secondary-btn"
            type="button"
            disabled={busy || form.steps.length >= 100}
            onClick={() => setForm(current => {
              const codes = new Set(current.steps.map(step => step.code));
              let suffix = current.steps.length + 1;
              while (codes.has(`STEP-${suffix}`)) suffix += 1;
              return { ...current, steps: [...current.steps, { ...newStep(current.steps.length), due_after_days: Number(current.steps.at(-1)?.due_after_days ?? 0) + 1, code: `STEP-${suffix}` }] };
            })}
          ><Plus size={15} /> Add step</button>
        </div>

        <div className="pathway-step-editors">
          {form.steps.map((step, index) => (
            <section className="pathway-step-editor" key={step.key}>
              <div className="pathway-step-editor-heading">
                <strong>Step {index + 1}</strong>
                <button className="icon-btn" type="button" aria-label={`Remove step ${index + 1}`} disabled={busy || form.steps.length === 1} onClick={() => setForm(current => ({ ...current, steps: current.steps.filter((_, i) => i !== index) }))}>
                  <Trash2 size={15} />
                </button>
              </div>
              <div className="pathway-form-grid pathway-step-fields">
                <label>Step code
                  <input required maxLength="100" value={step.code} onChange={event => updateStep(index, "code", event.target.value)} placeholder="CALL-24H" />
                </label>
                <label>Step name
                  <input required maxLength="200" value={step.name} onChange={event => updateStep(index, "name", event.target.value)} placeholder="Follow-up call" />
                </label>
                <label>Step type
                  <input required maxLength="50" value={step.step_type} onChange={event => updateStep(index, "step_type", event.target.value)} placeholder="FOLLOWUP" />
                </label>
                <div className="pathway-owner-field">
                  <span>Responsible role</span>
                  <Select
                    label="Responsible role"
                    value={step.owner_role}
                    onChange={value => updateStep(index, "owner_role", value)}
                    options={OWNER_ROLE_OPTIONS}
                    className="pathway-owner-select"
                  />
                </div>
                <label>Target day from journey start
                  <input required type="number" min="0" max="365" value={step.due_after_days} onChange={event => updateStep(index, "due_after_days", event.target.value)} />
                </label>
                <DurationInput label="Time allowed once ready" hours={step.time_limit_hours} onChange={value => updateStep(index, "time_limit_hours", value)} />
                <label className="pathway-description-field">Step details
                  <textarea rows="2" maxLength="2000" value={step.description} onChange={event => updateStep(index, "description", event.target.value)} placeholder="What needs to be done?" />
                </label>
              </div>
            </section>
          ))}
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="primary-btn" type="submit" disabled={busy}>{busy ? "Creating…" : "Create active pathway"}</button>
      </form>
    </Panel>

    <Panel wide title="Existing pathways" subtitle={`${pathways.data?.total ?? rows.length} pathway templates`}>
      {pathways.error ? <ErrorState error={pathways.error} title="Could not load pathways" /> :
        pathways.loading ? <div className="skeleton-list"><div className="skeleton-row"><i /><i /><i /><i /></div></div> :
          rows.length ? <div className="pathway-list">
            {rows.map(pathway => (
              <details className="pathway-list-item" key={pathway.id}>
                <summary>
                  <span><strong>{pathway.name}</strong><small><code>{pathway.code}</code> · v{pathway.version} · {pathway.steps?.length || 0} steps</small></span>
                  <span className="pathway-list-actions">
                    <Badge kind="status" value={pathway.status} />
                    {pathway.status === "ACTIVE" && <button className="secondary-btn pathway-edit-btn" type="button" aria-label={`Edit ${pathway.name}`} onClick={event => { event.preventDefault(); setEditing(pathway); }}><Pencil size={14} /> Edit</button>}
                  </span>
                </summary>
                <ol className="pathway-list-steps">
                  {(pathway.steps || []).map(step => (
                    <li key={step.id}>
                      <span><strong>{step.sequence_number}. {step.name}</strong><small>{step.description || humanize(step.step_type)}{step.required ? " · Required" : " · Optional"} · Owner: {humanize(step.owner_role || "CLINICIAN")}</small></span>
                      <span>{milestoneLabel(step.due_after_days)} · {formatDurationHours(step.time_limit_hours)} allowed</span>
                    </li>
                  ))}
                </ol>
              </details>
            ))}
          </div> : <EmptyState small title="No pathways found" text="Create the first pathway above." />}
      {!pathways.loading && !pathways.error && <Pagination offset={offset} count={rows.length} total={pathways.data?.total ?? 0} onPage={setOffset} />}
    </Panel>
    {editing && <PathwayEditDrawer key={editing.id} pathway={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); pathways.refetch().catch(() => {}); }} />}
  </div>;
}
