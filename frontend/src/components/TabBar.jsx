/**
 * TabBar — accessible tab strip shared by My Journey and Patients.
 * Purely presentational: selection state lives in the parent via `active` /
 * `onChange` (see hooks/useTabs).
 */
export default function TabBar({ tabs, active, onChange, className = "" }) {
  return (
    <div className={`tab-bar ${className}`.trim()} role="tablist">
      {tabs.map(({ id, label, icon: Icon, count }) => (
        <button key={id} role="tab" aria-selected={active === id}
          className={`tab-btn ${active === id ? "tab-btn--active" : ""}`}
          onClick={() => onChange(id)}>
          {Icon && <Icon size={15} />}
          {label}
          {count != null && count > 0 && <span className="tab-count">{count}</span>}
        </button>
      ))}
    </div>
  );
}
