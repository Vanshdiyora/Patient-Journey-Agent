import React from "react";
import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

export default function Forbidden() {
  return (
    <div className="not-found">
      <ShieldAlert size={44} />
      <span className="eyebrow">403</span>
      <h1>Access denied</h1>
      <p>Your role does not have permission to view this page.</p>
      <Link className="primary-btn" to="/">Back to home</Link>
    </div>
  );
}
