import React from "react";
import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import ChatWidget from "../components/chat/ChatWidget";
import { useAuth } from "../context/AuthContext";
import { portalFor } from "./portals";

/**
 * AppLayout â€” shell composing Sidebar, Topbar and routed page content.
 * Owns the mobile drawer state so both the Topbar menu button and the
 * Sidebar's own toggle can control it.
 */
export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();
  const portal = portalFor(user);

  return (
    <div className={`app-shell ${portal.theme}`}>
      <Sidebar mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} />
      <main className="main-area">
        <Topbar onOpenMenu={() => setMobileOpen(true)} />
        <div className="page-container"><Outlet /></div>
      </main>
      <ChatWidget />
    </div>
  );
}
