import { useState } from "react";
import { NavLink } from "react-router-dom";
import { LogOut, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import { portalFor } from "./portals";
import { isAdmin, roleOf } from "../utils/roles";

/**
 * Sidebar — themed per portal, desktop collapsible rail + mobile drawer.
 * Collapsed rail: logo and toggle share one slot; hovering the brand swaps
 * the logo for the open-sidebar button.
 * Bottom: role chip beside the user's name (identity card) and sign out.
 * The role chip mirrors the signed-in user's role; it is display-only —
 * the backend authorizes every API regardless of what the UI renders.
 */
export default function Sidebar({ mobileOpen, setMobileOpen }) {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();

  const portal = portalFor(user);
  const expanded = !collapsed || mobileOpen;
  const railMode = collapsed && !mobileOpen;
  const items = portal.items.filter(i => !i.adminOnly || isAdmin(user));

  const displayName = user?.name || user?.email || "User";
  const initials = displayName.split(" ").map(x => x[0]).slice(0, 2).join("").toUpperCase();
  const roleLabel = portal.roleLabel || roleOf(user);

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
          {expanded ? (
            user && (
              <div className="sidebar-usercard" title={`${displayName} — ${roleLabel}`}>
                <div className="sidebar-user-avatar">{initials}</div>
                <div className="sidebar-user-meta">
                  <span className="sidebar-user-name">{displayName}</span>
                  <span className={`role-chip role-chip--${portal.id}`}>{roleLabel}</span>
                </div>
                <span className="online-dot" title="Online" />
              </div>
            )
          ) : (
            user && (
              <div className="sidebar-usercard sidebar-usercard--rail" title={`${displayName} — ${roleLabel}`}>
                <div className="sidebar-user-avatar">{initials}</div>
              </div>
            )
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
