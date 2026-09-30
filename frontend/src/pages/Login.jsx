import React, { useState } from "react";
import { ArrowRight, CheckCircle2, Eye, EyeOff, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import { getErrorMessage } from "../utils/constants";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [entraObjectId, setEntraObjectId] = useState("");
  const [showId, setShowId] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !entraObjectId.trim()) {
      setError("Enter both your email and identity ID.");
      return;
    }
    setLoading(true);
    try {
      await login({ email: email.trim(), entra_object_id: entraObjectId.trim() });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-art">
        <div className="login-glow login-glow--one" /><div className="login-glow login-glow--two" />
        <div className="login-art-content">
          <div className="brand brand--light"><Brand /></div>
          <div className="hero-copy">
            <span className="eyebrow"><Sparkles size={15} /> Intelligent care coordination</span>
            <h1>Make every patient journey <em>visible.</em></h1>
            <p>One operational view for pathways, exceptions, automation and agent-assisted care coordination.</p>
          </div>
          <div className="login-features">
            <div><CheckCircle2 size={18} /><span>Real-time journey visibility</span></div>
            <div><CheckCircle2 size={18} /><span>Deterministic orchestration</span></div>
            <div><CheckCircle2 size={18} /><span>Auditable agent activity</span></div>
          </div>
        </div>
        <div className="login-art-footer">Secure clinical operations workspace</div>
      </div>

      <div className="login-panel">
        <div className="login-card">
          <div className="mobile-brand"><Brand /><strong>Patient</strong></div>
          <div className="login-heading">
            <span className="eyebrow eyebrow--teal">Welcome back</span>
            <h2>Sign in to your workspace</h2>
            <p>Patients and care teams can sign in with their registered account.</p>
          </div>
          <form onSubmit={submit} className="form-stack">
            <label>Email address
              <div className="input-wrap"><Mail size={18} /><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.test" autoComplete="email" /></div>
            </label>
            <label>Identity ID
              <div className="input-wrap"><LockKeyhole size={18} /><input type={showId ? "text" : "password"} value={entraObjectId} onChange={e => setEntraObjectId(e.target.value)} placeholder="Your Entra or demo identity ID" autoComplete="off" />
                <button type="button" className="input-action" onClick={() => setShowId(!showId)}>{showId ? <EyeOff size={17} /> : <Eye size={17} />}</button>
              </div>
            </label>
            {error && <div className="form-error"><span className="error-icon">!</span>{error}</div>}
            <button className="primary-btn primary-btn--full" disabled={loading}>
              {loading ? <><span className="button-spinner" />Signing in…</> : <>Continue <ArrowRight size={18} /></>}
            </button>
          </form>
          <div className="secure-note"><ShieldCheck size={17} /><span>Identity is verified by the CarePath backend.</span></div>
        </div>
      </div>
    </div>
  );
}
