import React, { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { pathwaysApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { getErrorMessage, humanize, toList } from "../../utils";
import { PageHeading, Panel, ErrorState, EmptyState, Badge } from "../../components";
import { useToast } from "../../context/ToastContext";

const newStep = (index) => ({
  code: `STEP-${index + 1}`,
  name: "",
  description: "",
  step_type: "FOLLOWUP",
  time_limit_hours: 24,
});

export default function Pathways() {
  const pathways = useAsync(() => pathwaysApi.list(), []);
  const toast = useToast();
  const [form, setForm] = useState({
    code: "",
    name: "",
    description: "",
    steps: [newStep(0)],
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const rows = toList(pathways.data);

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
          ...step,
          code: step.code.trim(),
          name: step.name.trim(),
          description: step.description.trim() || null,
          step_type: step.step_type.trim(),
          sequence_number: index + 1,
          time_limit_hours: Number(step.time_limit_hours),
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
      description="Create reusable pathways with ordered steps and a time limit for each step."
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
          <div><strong>Pathway steps</strong><span>Each timer begins when its step becomes ready.</span></div>
          <button
            className="secondary-btn"
            type="button"
            disabled={busy || form.steps.length >= 100}
            onClick={() => setForm(current => ({ ...current, steps: [...current.steps, newStep(current.steps.length)] }))}
          ><Plus size={15} /> Add step</button>
        </div>

        <div className="pathway-step-editors">
          {form.steps.map((step, index) => (
            <section className="pathway-step-editor" key={index}>
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
                <label>Time limit (hours)
                  <input required type="number" min="1" max="8760" value={step.time_limit_hours} onChange={event => updateStep(index, "time_limit_hours", event.target.value)} />
                </label>
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

    <Panel wide title="Existing pathways" subtitle={`${rows.length} pathway templates`}>
      {pathways.error ? <ErrorState error={pathways.error} title="Could not load pathways" /> :
        pathways.loading ? <div className="skeleton-list"><div className="skeleton-row"><i /><i /><i /><i /></div></div> :
          rows.length ? <div className="pathway-list">
            {rows.map(pathway => (
              <details className="pathway-list-item" key={pathway.id}>
                <summary>
                  <span><strong>{pathway.name}</strong><small><code>{pathway.code}</code> · v{pathway.version} · {pathway.steps?.length || 0} steps</small></span>
                  <Badge kind="status" value={pathway.status} />
                </summary>
                <ol className="pathway-list-steps">
                  {(pathway.steps || []).map(step => (
                    <li key={step.id}>
                      <span><strong>{step.sequence_number}. {step.name}</strong><small>{step.description || humanize(step.step_type)}{step.required ? " · Required" : " · Optional"}</small></span>
                      <span>{step.time_limit_hours} hours</span>
                    </li>
                  ))}
                </ol>
              </details>
            ))}
          </div> : <EmptyState small title="No pathways found" text="Create the first pathway above." />}
    </Panel>
  </div>;
}
