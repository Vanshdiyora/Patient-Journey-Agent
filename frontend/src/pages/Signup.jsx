import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Calendar, CheckCircle2, ChevronDown, LockKeyhole, Mail, ShieldCheck, Sparkles, User as UserIcon } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../services";
import Brand from "../components/Brand";
import { getErrorMessage } from "../utils";
import { ROLES } from "../utils/roles";

const ROLE_OPTIONS = [
  { value: ROLES.PATIENT, label: "Patient" },
  { value: ROLES.CLINICIAN, label: "Clinician" },
  { value: ROLES.CARE_COORDINATOR, label: "Care Coordinator" },
  { value: ROLES.ADMIN, label: "Administrator" },
];

const GENDER_OPTIONS = ["Female", "Male", "Non-binary", "Prefer not to say"];

export default function Signup() {
  const { login } = useAuth();
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    role: ROLES.PATIENT,
    dob: "",
    gender: GENDER_OPTIONS[0],
    password: "",
    confirm: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.firstName.trim() || !form.lastName.trim()) {
      setError("Enter your first and last name.");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (form.password !== form.confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (form.role === ROLES.PATIENT && !form.dob) {
      setError("Date of birth is required for patient accounts.");
      return;
    }
    setLoading(true);
    try {
      // Create the account, then sign straight in so the new user lands
      // directly in their portal.
      await authApi.signup({
        first_name: form.firstName.trim(),
        last_name: form.lastName.trim(),
        email: form.email.trim(),
        role: form.role,
        password: form.password,
        date_of_birth: form.role === ROLES.PATIENT ? form.dob : undefined,
        gender: form.role === ROLES.PATIENT ? form.gender : undefined,
      });
      await login({ email: form.email.trim(), password: form.password });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const isPatient = form.role === ROLES.PATIENT;

  return (
    <div className="login-page">
      <div className="login-art">
        <div className="login-glow login-glow--one" /><div className="login-glow login-glow--two" />
        <div className="login-art-content">
          <div className="brand brand--light"><Brand /></div>
          <div className="hero-copy">
            <span className="eyebrow"><Sparkles size={15} /> Join CarePath</span>
            <h1>Your care journey, <em>one workspace away.</em></h1>
            <p>Create an account to follow journeys, record updates and coordinate care in real time.</p>
          </div>
          <div className="login-features">
            <div><CheckCircle2 size={18} /><span>Real-time journey visibility</span></div>
            <div><CheckCircle2 size={18} /><span>Secure patient portal</span></div>
            <div><CheckCircle2 size={18} /><span>AI-assisted coordination</span></div>
          </div>
        </div>
        <div className="login-art-footer">Secure clinical operations workspace</div>
      </div>

      <div className="login-panel">
        <div className="login-card">
          <div className="mobile-brand"><Brand /><strong>Patient</strong></div>
          <div className="login-heading">
            <span className="eyebrow eyebrow--teal">Get started</span>
            <h2>Create your account</h2>
            <p>A few details and you're in. Already registered? <Link to="/login" className="text-link">Sign in</Link></p>
          </div>
          <form onSubmit={submit} className="form-stack">
            <div className="form-row">
              <label>First name
                <div className="input-wrap"><UserIcon size={18} /><input value={form.firstName} onChange={set("firstName")} placeholder="Maya" autoComplete="given-name" /></div>
              </label>
              <label>Last name
                <div className="input-wrap"><UserIcon size={18} /><input value={form.lastName} onChange={set("lastName")} placeholder="Chen" autoComplete="family-name" /></div>
              </label>
            </div>
            <label>Email address
              <div className="input-wrap"><Mail size={18} /><input type="email" value={form.email} onChange={set("email")} placeholder="name@example.test" autoComplete="email" /></div>
            </label>
            <label>I am a
              <div className="input-wrap">
                <ShieldCheck size={18} />
                <select className="signup-role-select" value={form.role} onChange={set("role")}>
                  {ROLE_OPTIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
                <ChevronDown size={16} className="input-action" />
              </div>
            </label>
            {isPatient && (
              <div className="form-row">
                <label>Date of birth
                  <div className="input-wrap"><Calendar size={18} /><input type="date" value={form.dob} onChange={set("dob")} max={new Date().toISOString().slice(0, 10)} /></div>
                </label>
                <label>Gender
                  <div className="input-wrap">
                    <UserIcon size={18} />
                    <select className="signup-role-select" value={form.gender} onChange={set("gender")}>
                      {GENDER_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                    <ChevronDown size={16} className="input-action" />
                  </div>
                </label>
              </div>
            )}
            <label>Password
              <div className="input-wrap"><LockKeyhole size={18} />
                <input type={showPassword ? "text" : "password"} value={form.password} onChange={set("password")} placeholder="At least 8 characters" autoComplete="new-password" />
                <button type="button" className="input-action" onClick={() => setShowPassword(s => !s)}>{showPassword ? "Hide" : "Show"}</button>
              </div>
            </label>
            <label>Confirm password
              <div className="input-wrap"><LockKeyhole size={18} /><input type={showPassword ? "text" : "password"} value={form.confirm} onChange={set("confirm")} placeholder="Repeat your password" autoComplete="new-password" /></div>
            </label>
            {error && <div className="form-error"><span className="error-icon">!</span>{error}</div>}
            <button className="primary-btn primary-btn--full" disabled={loading}>
              {loading ? <><span className="button-spinner" />Creating account…</> : <>Create account <ArrowRight size={18} /></>}
            </button>
          </form>
          <div className="secure-note"><ShieldCheck size={17} /><span>Your password is stored only as a bcrypt hash.</span></div>
        </div>
      </div>
    </div>
  );
}
