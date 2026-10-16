import React, { useState } from "react";
import { ArrowRight, CheckCircle2, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "../../../context/AuthContext";
import Brand from "../../../components/Brand";
import { getErrorMessage } from "../../../utils/index";

const DEMO_PASSWORD = "Test@123";
const DEMO_ACCOUNTS = [
  { role: "Administrator", email: "a.ansari0884@carepath-health.example" },
  { role: "Clinician", email: "a.ansari0084@carepath-health.example" },
  { role: "Care coordinator", email: "a.ansari0284@carepath-health.example" },
  { role: "Patient", email: "abhi@gmail.com" },
];
const SHOW_DEMO_LOGIN = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEMO_LOGIN === "true";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const signIn = async (credentials) => {
    if (loading) return;
    setError("");
    if (!credentials.email || !credentials.password) {
      setError("Enter your email and password.");
      return;
    }
    setLoading(true);
    try {
      await login(credentials);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const submit = (event) => {
    event.preventDefault();
    signIn({ email: email.trim(), password });
  };

  const signInAsDemo = (account) => {
    setEmail(account.email);
    setPassword(DEMO_PASSWORD);
    signIn({ email: account.email, password: DEMO_PASSWORD });
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
          {SHOW_DEMO_LOGIN && (
            <div className="demo-login">
              <div className="demo-login-heading">
                <strong>Demo accounts</strong>
                <span>Choose a role to sign in. Shared password: {DEMO_PASSWORD}</span>
              </div>
              <div className="demo-login-grid">
                {DEMO_ACCOUNTS.map(account => (
                  <button
                    type="button"
                    className="demo-login-account"
                    key={account.role}
                    onClick={() => signInAsDemo(account)}
                    disabled={loading}
                    aria-label={`Sign in as ${account.role} using ${account.email}`}
                  >
                    <span><strong>{account.role}</strong><small>{account.email}</small></span>
                    <ArrowRight size={16} aria-hidden="true" />
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="secure-note"><ShieldCheck size={17} /><span>Identity is verified by the CarePath backend.</span></div>
          <p className="login-switch">Patient accounts are created by an administrator. Ask your care team for your sign-in details.</p>
        </div>
      </div>
    </div>
  );
}
