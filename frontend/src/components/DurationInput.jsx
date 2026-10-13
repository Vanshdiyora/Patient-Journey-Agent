import React, { useId, useState } from "react";
import { durationHoursFromParts, splitDurationHours } from "../utils/duration";

const MAX_DURATION_HOURS = 8760;

export default function DurationInput({ label, hours, onChange, disabled = false, className = "" }) {
  const id = useId();
  const [editing, setEditing] = useState(null);
  const parts = hours === "" || hours == null ? null : splitDurationHours(hours);
  const updatePart = (part, value) => {
    setEditing({ part, value });
    const current = parts || { weeks: 0, days: 0, hours: 0 };
    const amount = value === "" ? 0 : Math.max(0, Math.floor(Number(value) || 0));
    const totalHours = durationHoursFromParts({ ...current, [part]: amount });
    onChange(Math.min(MAX_DURATION_HOURS, totalHours));
  };

  return <div className={`duration-field ${className}`.trim()}>
    <span className="duration-field-label">{label}</span>
    <div className="duration-controls">
      {[
        ["weeks", 52],
        ["days", 6],
        ["hours", 23],
      ].map(([part, max]) => (
        <label className="duration-part" htmlFor={`${id}-${part}`} key={part}>
          <input id={`${id}-${part}`} aria-label={`${label}: ${part}`} type="number" min="0" max={max} step="1"
            value={editing?.part === part ? editing.value : parts ? parts[part] : ""} disabled={disabled}
            onChange={event => updatePart(part, event.target.value)} onBlur={() => setEditing(null)} />
          <span>{part}</span>
        </label>
      ))}
    </div>
  </div>;
}
