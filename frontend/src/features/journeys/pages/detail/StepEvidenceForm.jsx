import React, { useRef, useState } from "react";
import { Paperclip, Upload } from "lucide-react";

const MAX_FILE_BYTES = 1024 * 1024;

export default function StepEvidenceForm({ step, busy, evidenceType = "RESULT", onSubmit }) {
  const [details, setDetails] = useState("");
  const [file, setFile] = useState(null);
  const [approvalConfirmed, setApprovalConfirmed] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef(null);

  const selectFile = (event) => {
    const selected = event.target.files?.[0] || null;
    if (selected && selected.size > MAX_FILE_BYTES) {
      setError("Files must be 1 MB or smaller.");
      event.target.value = "";
      setFile(null);
      return;
    }
    setError("");
    setFile(selected);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!details.trim() && !file) {
      setError("Add evidence details or attach a file.");
      return;
    }
    setError("");
    const saved = await onSubmit(step, details.trim(), file, evidenceType, approvalConfirmed);
    if (saved) {
      setDetails("");
      setFile(null);
      setApprovalConfirmed(false);
      formRef.current?.reset();
    }
  };

  return (
    <form ref={formRef} className="step-evidence-form" onSubmit={submit}>
      <strong><Paperclip size={13} />{evidenceType === "APPROVAL" ? "Record approval evidence" : "Add evidence"}</strong>
      <label>
        Details
        <textarea
          value={details}
          onChange={event => setDetails(event.target.value)}
          maxLength={4000}
          rows={2}
          placeholder={evidenceType === "APPROVAL" ? "Who approved it, when, and any relevant reference…" : "Record the result or checklist evidence…"}
          disabled={busy}
        />
      </label>
      <label>
        Attach file (optional, max 1 MB)
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
          onChange={selectFile}
          disabled={busy}
        />
      </label>
      {file && <span className="step-evidence-file">{file.name}</span>}
      {evidenceType === "APPROVAL" && <label className="step-evidence-confirm">
        <input
          type="checkbox"
          checked={approvalConfirmed}
          onChange={event => setApprovalConfirmed(event.target.checked)}
          disabled={busy}
          required
        />
        I confirm the required approval has actually been received.
      </label>}
      {error && <span className="event-form-error">{error}</span>}
      <button className="secondary-btn" type="submit" disabled={busy || (!details.trim() && !file) || (evidenceType === "APPROVAL" && !approvalConfirmed)}>
        <Upload size={13} />{busy ? "Saving evidence…" : evidenceType === "APPROVAL" ? "Save approval evidence" : "Save evidence"}
      </button>
      <small>Evidence is stored privately. It may make this step eligible, but does not mark it complete. Authorized staff can download attached files.</small>
    </form>
  );
}
