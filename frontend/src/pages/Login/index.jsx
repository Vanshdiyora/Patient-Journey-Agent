import React, { useState } from "react";
import { ArrowRight, CheckCircle2, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import Brand from "../../components/Brand";
import { getErrorMessage } from "../../utils";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setLoading(true);
    try {
      await login({ email: email.trim(), password });
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
            <p>Sign in with the email address and password for your account.</p>
          </div>
          <form onSubmit={submit} className="form-stack">
            <label>Email address
              <div className="input-wrap"><Mail size={18} /><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.test" autoComplete="email" /></div>
            </label>
            <label>Password
              <div className="input-wrap"><LockKeyhole size={18} /><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" autoComplete="current-password" />
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
