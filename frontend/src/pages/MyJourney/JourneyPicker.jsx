import React from "react";
import { humanize } from "../../utils";

/** Journey switcher shown when the patient has more than one journey. */
export default function JourneyPicker({ journeys, currentId, onSelect }) {
  if (!journeys?.length || journeys.length < 2) return null;
  return (
    <div className="button-group" style={{ marginBottom: 16 }}>
      {journeys.map(j => (
        <button key={j.id} className={j.id === currentId ? "primary-btn" : "secondary-btn"} onClick={() => onSelect(j.id)}>
          {humanize(j.pathway_name || "Care journey")}
        </button>
      ))}
    </div>
  );
}
