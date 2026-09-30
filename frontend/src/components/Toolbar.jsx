import React from "react";
import { Search } from "lucide-react";

/**
 * Toolbar building blocks for list pages.
 */

export function SearchBox({ value, onChange, placeholder = "Searchâ€¦" }) {
  return (
    <div className="search-field">
      <Search size={17} />
      <input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  );
}

export function FilterSelect({ label, value, onChange, options }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} aria-label={label}>
      <option value="">{label}</option>
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  );
}

export function ResultCount({ icon: Icon, children }) {
  return (
    <span className="result-count">
      {Icon && <Icon size={15} />}
      {children}
    </span>
  );
}
