import { useState } from "react";
import { NavLink } from "react-router-dom";
import { LogOut, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import { portalFor } from "./portals";
import { isAdmin } from "../utils/roles";

/**
 * Sidebar — themed per portal, desktop collapsible rail + mobile drawer.
 * Collapsed rail: logo and toggle share one slot; hovering the brand swaps
 * the logo for the open-sidebar button.
 */
export default function Sidebar({ mobileOpen, setMobileOpen }) {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();

  const portal = portalFor(user);
  const expanded = !collapsed || mobileOpen;
  const railMode = collapsed && !mobileOpen;
  const items = portal.items.filter(i => !i.adminOnly || isAdmin(user));

  const handleToggle = () => {
    if (window.matchMedia("(max-width: 820px)").matches) {
      setMobileOpen(false);
      return;
    }
    setCollapsed(c => !c);
  };

  const closeMobile = () => setMobileOpen(false);

  return (
    <>
      <aside className={`sidebar ${collapsed ? "sidebar--collapsed" : ""} ${mobileOpen ? "sidebar--mobile-open" : ""}`}>
        <div className="brand">
          <Brand />
          {expanded && (
            <div>
              <strong>Patient</strong>
              <small>{portal.label}</small>
            </div>
          )}
          <button className="icon-btn sidebar-toggle" onClick={handleToggle}
            aria-label={railMode ? "Open sidebar" : mobileOpen ? "Close menu" : "Close sidebar"}
            title={railMode ? "Open sidebar" : mobileOpen ? "Close menu" : "Close sidebar"}>
            {mobileOpen ? <X size={19} /> : railMode ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
          </button>
        </div>

        {expanded && <div className="workspace-label">{portal.label}</div>}
        <nav className="sidebar-nav">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={closeMobile}
              title={railMode ? label : undefined}
              className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <Icon size={19} strokeWidth={2} />
              {expanded && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          {expanded && user && (
            <div className="sidebar-status">
              <span className="online-dot" /> {user.name || user.email}
            </div>
          )}
          <button className="nav-item" onClick={logout}>
            <LogOut size={19} />
            {expanded && <span>Sign out</span>}
          </button>
        </div>
      </aside>

      {mobileOpen && <div className="mobile-overlay" onClick={closeMobile} />}
    </>
  );
}
