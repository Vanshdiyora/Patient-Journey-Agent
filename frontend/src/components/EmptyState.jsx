import React from "react";
/**
 * EmptyState â€” "nothing here" placeholder with icon, title, and hint text.
 */
export default function EmptyState({ icon: Icon, title, text, small = false }) {
  return (
    <div className={`empty-state ${small ? "empty-state--small" : ""}`.trim()}>
      {Icon && <Icon size={small ? 24 : 30} />}
      <strong>{title}</strong>
      {text && <span>{text}</span>}
    </div>
  );
}
