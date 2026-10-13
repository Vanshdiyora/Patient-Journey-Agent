import React, { useId, useState } from "react";
import { preferredUnit } from "../utils/duration";

const HOURS_PER_UNIT = { hours: 1, days: 24, weeks: 168 };

export default function DurationInput({ label, hours, onChange, disabled = false, className = "" }) {
  const id = useId();
  const [unit, setUnit] = useState(() => preferredUnit(hours));
  const factor = HOURS_PER_UNIT[unit];
  const amount = hours === "" || hours == null ? "" : Number((Number(hours) / factor).toFixed(2));
  return <div className={`duration-field ${className}`.trim()}>
    <label htmlFor={id}>{label}</label>
    <div className="duration-controls">
      <input id={id} aria-label={label} type="number" min="0.01" max={8760 / factor} step="any" required
        value={amount} disabled={disabled}
        onChange={event => onChange(event.target.value === "" ? "" : Math.max(1, Math.round(Number(event.target.value) * factor)))} />
      <select aria-label={`${label} unit`} value={unit} disabled={disabled} onChange={event => setUnit(event.target.value)}>
        <option value="hours">hours</option><option value="days">days</option><option value="weeks">weeks</option>
      </select>
    </div>
  </div>;
}
