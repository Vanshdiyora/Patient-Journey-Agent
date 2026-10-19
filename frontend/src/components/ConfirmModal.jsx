import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, HelpCircle, Loader2 } from "lucide-react";

/**
 * Reusable confirmation modal for important actions.
 *
 * Use via the useConfirm hook:
 *   const confirm = useConfirm();
 *   const ok = await confirm({ title: "Sign out?", message: "...", intent: "danger" });
 *   if (ok) doIt();
 *
 * intent: "danger" (red) | "primary" (teal)
 */
export function ConfirmModal({
  open, title, message, confirmLabel = "Confirm", cancelLabel = "Cancel",
  intent = "primary", busy = false, onConfirm, onCancel,
}) {
  const cardRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    cardRef.current?.querySelector("button")?.focus();
    const onKey = (e) => {
      if (e.key === "Escape" && !busy) onCancel();
      if (e.key !== "Tab") return;
      const buttons = [...cardRef.current.querySelectorAll("button:not([disabled])")];
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={() => !busy && onCancel()}>
      <div ref={cardRef} className="modal-card" role="alertdialog" aria-modal="true" aria-label={title} onClick={e => e.stopPropagation()}>
        <div className={`modal-icon modal-icon--${intent}`}>
          {intent === "danger" ? <AlertTriangle size={22} /> : <HelpCircle size={22} />}
        </div>
        <h3 className="modal-title">{title}</h3>
        {message && <p className="modal-message">{message}</p>}
        <div className="modal-actions">
          <button className="secondary-btn" disabled={busy} onClick={onCancel}>{cancelLabel}</button>
          <button
            className={intent === "danger" ? "danger-btn" : "primary-btn"}
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? <Loader2 size={15} className="spin-inline" /> : null}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Promise-based confirm hook so pages can `await confirm(...)` inline. */
export function useConfirm() {
  const [state, setState] = useState(null); // {title, message, ..., resolve}
  const busyRef = useRef(false);

  const confirm = useCallback((options) => new Promise((resolve) => {
    setState({ ...options, resolve });
  }), []);

  const close = useCallback((result) => {
    setState(prev => {
      prev?.resolve?.(result);
      return null;
    });
    busyRef.current = false;
  }, []);

  const element = state ? (
    <ConfirmModal
      open
      busy={busyRef.current}
      title={state.title}
      message={state.message}
      confirmLabel={state.confirmLabel}
      cancelLabel={state.cancelLabel}
      intent={state.intent}
      onConfirm={() => close(true)}
      onCancel={() => close(false)}
    />
  ) : null;

  return [confirm, element];
}
