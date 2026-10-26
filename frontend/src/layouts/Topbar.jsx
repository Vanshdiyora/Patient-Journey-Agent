import { ChevronRight, Menu, Search } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { portalFor } from "./portals";
import { isAdmin } from "../utils/roles";
import NotificationCenter from "../features/notifications/components/NotificationCenter";

/**
 * Topbar — sticky header with portal label, breadcrumb, search and avatar.
 */
export default function Topbar({ onOpenMenu }) {
  const location = useLocation();
  const { user } = useAuth();
  const portal = portalFor(user);

  const items = portal.items.filter(i => !i.adminOnly || isAdmin(user));
  const current = items.find(n => n.end ? location.pathname === n.to : location.pathname.startsWith(n.to));
  const displayName = user?.name || user?.email?.split("@")[0] || "Care team";
  const initials = displayName.split(" ").map(x => x[0]).slice(0, 2).join("").toUpperCase();

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-btn mobile-menu-btn" onClick={onOpenMenu} aria-label="Open menu"><Menu size={21} /></button>
        <div className="breadcrumb">
          <span>{portal.label}</span><ChevronRight size={14} /><strong>{current?.label || "Workspace"}</strong>
        </div>
      </div>
      <div className="topbar-right">
        <div className="global-search"><Search size={17} /><input placeholder="Search patients, journeys…" /><kbd>⌘ K</kbd></div>
        <NotificationCenter />
        <div className="avatar" title={`${displayName} — ${portal.label}`}>{initials}</div>
      </div>
    </header>
  );
}
