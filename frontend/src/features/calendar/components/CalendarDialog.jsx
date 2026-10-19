import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

/** Focus containment, escape, and focus restoration for calendar dialogs. */
export default function CalendarDialog({ title, onClose, busy = false, children }) {
  const card = useRef(null);
  const close = useRef(null);
  const returnFocus = useRef(document.activeElement);
  const state = useRef({ onClose, busy });
  state.current = { onClose, busy };
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    close.current?.focus();
    const onKey = event => {
      // The shared confirmation dialog sits above this dialog.
      if (document.querySelector(".modal-backdrop")) return;
      if (event.key === "Escape" && !state.current.busy) state.current.onClose();
      if (event.key !== "Tab") return;
      const focusable = [...card.current.querySelectorAll("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled])")];
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
      if (returnFocus.current?.isConnected) returnFocus.current.focus();
    };
  }, []);
  return createPortal(<div className="calendar-dialog-backdrop" onMouseDown={event => {
    if (event.target === event.currentTarget && !busy) onClose();
  }}>
    <section ref={card} className="calendar-dialog" role="dialog" aria-modal="true" aria-labelledby="calendar-dialog-title">
      <header><h2 id="calendar-dialog-title">{title}</h2><button ref={close} className="icon-btn" type="button" aria-label="Close activity" disabled={busy} onClick={onClose}><X size={18} /></button></header>
      {children}
    </section>
  </div>, document.body);
}
