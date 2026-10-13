import React, { useState } from "react";
import { authApi } from "../services";
import { getErrorMessage } from "../utils";
import { PageHeading, Panel } from "../components";

export default function Account() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const submit = async event => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await authApi.changePassword({ current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage("Password changed. Use your new password next time you sign in.");
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setBusy(false);
    }
  };

  return <div>
    <PageHeading eyebrow="Account" title="Change password" description="Replace your temporary password with one you choose." />
    <Panel title="Password">
      <form className="form-stack" style={{ padding: 18 }} onSubmit={submit}>
        <label>Current password<input type="password" autoComplete="current-password" required value={current} onChange={event => setCurrent(event.target.value)} /></label>
        <label>New password<input type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={next} onChange={event => setNext(event.target.value)} /></label>
        <label>Confirm new password<input type="password" autoComplete="new-password" required value={confirm} onChange={event => setConfirm(event.target.value)} /></label>
        {error && <div className="form-error" role="alert">{error}</div>}
        {message && <div role="status">{message}</div>}
        <button className="primary-btn" disabled={busy}>{busy ? "Saving…" : "Change password"}</button>
      </form>
    </Panel>
  </div>;
}
