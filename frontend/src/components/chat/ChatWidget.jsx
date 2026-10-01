import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Archive, Bot, ChevronLeft, Loader2, MessageCircle, Mic, MicOff, Plus,
  Send, X,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { chatApi, openChatSocket } from "../../services/chat";
import { useConfirm } from "../ConfirmModal";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../utils";
import ChatMessageItem from "./ChatMessageItem";

const VOICE_LANG = "en-US";

/**
 * Floating assistant available in every portal. Transport prefers the
 * WebSocket; falls back to REST if the socket is not open. All role scoping
 * is enforced server-side — the UI only mirrors it (e.g. patient-safe
 * actions, staff-only orchestration surfaces).
 */
export default function ChatWidget() {
  const { user, token } = useAuth();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState("chat"); // chat | history
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [launcherGreeting, setLauncherGreeting] = useState(false);
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();

  const scrollRef = useRef(null);
  const socketRef = useRef(null);
  const recognitionRef = useRef(null);
  const sessionRef = useRef(null);
  sessionRef.current = sessionId;

  const isPatient = user?.role?.toUpperCase() === "PATIENT";

  // ------------------------------------------------------------------ data

  const loadSessions = useCallback(() => {
    chatApi.listSessions()
      .then(r => setSessions(r.items || []))
      .catch(() => setSessions([]));
  }, []);

  const loadMessages = useCallback((id) => {
    if (!id) return;
    chatApi.messages(id)
      .then(r => setMessages(r.items || []))
      .catch(() => setMessages([]));
  }, []);

  const startNewChat = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setView("chat");
    setError("");
  }, []);

  const openSession = useCallback((id) => {
    setSessionId(id);
    loadMessages(id);
    setView("chat");
  }, [loadMessages]);

  useEffect(() => {
    if (open) loadSessions();
  }, [open, loadSessions]);

  // Scroll to bottom on new messages/typing state.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, typing, open]);

  // ------------------------------------------------------------ websocket

  const ensureSocket = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      return socketRef.current;
    }
    const socket = openChatSocket({
      onEvent: (event) => {
        if (event.type === "typing") setTyping(true);
        if (event.type === "message") {
          setTyping(false);
          setSending(false);
          const sid = event.session_id;
          if (sid && sid !== sessionRef.current) setSessionId(sid);
          setMessages(prev => [...prev, event.user_message, event.assistant_message]);
        }
        if (event.type === "error") {
          setTyping(false);
          setSending(false);
          setError(event.detail || "Something went wrong.");
        }
      },
      onClose: () => { socketRef.current = null; },
    });
    socketRef.current = socket;
    return socket;
  }, []);

  const sendViaSocket = (socket, content) => new Promise((resolve, reject) => {
    const onFrame = (e) => {
      let frame;
      try { frame = JSON.parse(e.data); } catch { return; }
      if (frame.type === "message" || frame.type === "error") {
        socket.removeEventListener("message", onFrame);
        frame.type === "error" ? reject(new Error(frame.detail)) : resolve(frame);
      }
    };
    socket.addEventListener("message", onFrame);
    socket.send(JSON.stringify({ type: "message", content, session_id: sessionId }));
  });

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || sending) return;
    setError("");
    setInput("");
    setMessages(prev => [...prev, {
      id: `local-${Date.now()}`, session_id: sessionId, role: "user",
      content, meta: null, created_at: new Date().toISOString(),
    }]);
    setSending(true);
    try {
      const socket = ensureSocket();
      if (socket.readyState === WebSocket.OPEN) {
        try {
          await sendViaSocket(socket, content);
          return;
        } catch {
          // fall through to REST fallback
        }
      }
      // REST fallback (also covers the very first message: socket not open yet).
      let sid = sessionId;
      if (!sid) {
        const created = await chatApi.createSession();
        sid = created.id;
        setSessionId(sid);
      }
      const result = await chatApi.sendMessage(sid, content);
      setMessages(prev => [...prev, result.user_message, result.assistant_message]);
      loadSessions();
    } catch (err) {
      setError(getErrorMessage(err));
      setMessages(prev => prev.filter(m => !m.id.startsWith("local-")));
      setInput(content); // restore the user's text so nothing is lost
    } finally {
      setSending(false);
      setTyping(false);
    }
  };

  // ------------------------------------------------------- action confirm

  const resolveAction = async (messageId, action) => {
    if (!sessionId || !messageId) return;
    setSending(true);
    try {
      const result = action === "confirm"
        ? await chatApi.confirmAction(sessionId, messageId)
        : await chatApi.rejectAction(sessionId, messageId);
      setMessages(prev => prev.map(m => (
        m.id === messageId ? result.message || result.confirmed_message : m
      )));
      if (result.result_message) setMessages(prev => [...prev, result.result_message]);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSending(false);
    }
  };

  // ------------------------------------------------------------ voice

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    setVoiceSupported(Boolean(SR));
  }, []);

  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = VOICE_LANG;
    recognition.interimResults = true;
    recognition.continuous = false;
    let finalText = "";
    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += chunk;
        else interim += chunk;
      }
      setInput((finalText + " " + interim).trim());
    };
    recognition.onend = () => {
      setListening(false);
      if (finalText.trim()) send(finalText.trim());
      finalText = "";
    };
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  };

  // ------------------------------------------------------- socket cleanup

  useEffect(() => () => {
    socketRef.current?.close();
    recognitionRef.current?.stop();
  }, []);

  const archive = async (id) => {
    const ok = await confirm({
      title: "Delete this conversation?",
      message: "The conversation will be removed from your history. This cannot be undone.",
      confirmLabel: "Delete",
      intent: "danger",
    });
    if (!ok) return;
    try {
      await chatApi.archiveSession(id);
      toast.success("Conversation deleted.");
      setSessions(prev => prev.filter(s => s.id !== id));
      if (id === sessionId) startNewChat();
      if (view === "history" && !sessions.length) setView("chat");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  // Launcher greeting bubble (first visit only, per tab).
  useEffect(() => {
    if (sessionStorage.getItem("carepath_chat_greeted")) return;
    const t = setTimeout(() => setLauncherGreeting(true), 2500);
    return () => clearTimeout(t);
  }, []);
  const dismissGreeting = () => {
    sessionStorage.setItem("carepath_chat_greeted", "1");
    setLauncherGreeting(false);
  };

  const greetingText = isPatient
    ? "Hi! I can help you record an update for your care team — type or say it."
    : "Hi! Ask me about your journeys, or tell me to record an update for a patient.";

  return (
    <>
      {/* Floating launcher */}
      <div className="chat-launcher-wrap">
        {launcherGreeting && !open && (
          <div className="chat-launcher-bubble" onClick={() => { dismissGreeting(); setOpen(true); }}>
            {greetingText}
            <button className="chat-launcher-bubble-close" onClick={(e) => { e.stopPropagation(); dismissGreeting(); }} aria-label="Dismiss">×</button>
          </div>
        )}
        <button
          className={`chat-launcher ${open ? "chat-launcher--active" : ""}`}
          onClick={() => { if (!open) { setOpen(true); dismissGreeting(); } else setOpen(false); }}
          aria-label={open ? "Close assistant" : "Open assistant"}
        >
          {open ? <X size={22} /> : <MessageCircle size={22} />}
        </button>
      </div>

      {/* Panel */}
      {open && (
        <div className="chat-panel" role="dialog" aria-label="CarePath assistant">
          {confirmModal}
          <div className="chat-header">
            {view === "history" ? (
              <>
                <button className="chat-icon-btn" onClick={() => setView("chat")} aria-label="Back to chat">
                  <ChevronLeft size={17} />
                </button>
                <div className="chat-header-title"><strong>History</strong><span>Your conversations</span></div>
              </>
            ) : (
              <>
                <div className="chat-header-avatar"><Bot size={16} /></div>
                <div className="chat-header-title">
                  <strong>CarePath Assistant</strong>
                  <span>{typing ? "typing…" : isPatient ? "Patient portal" : "Staff portal"}</span>
                </div>
                <button className="chat-icon-btn" onClick={startNewChat} aria-label="New conversation" title="New conversation"><Plus size={17} /></button>
                <button className="chat-icon-btn" onClick={() => { loadSessions(); setView("history"); }} aria-label="History" title="History"><Archive size={17} /></button>
              </>
            )}
            <button className="chat-icon-btn" onClick={() => setOpen(false)} aria-label="Close assistant"><X size={17} /></button>
          </div>

          {view === "history" ? (
            <div className="chat-history-list">
              {sessions.length === 0 && <div className="chat-empty">No conversations yet.</div>}
              {sessions.map(s => (
                <div key={s.id} className={`chat-history-item ${s.id === sessionId ? "chat-history-item--active" : ""}`}>
                  <button className="chat-history-main" onClick={() => openSession(s.id)}>
                    <strong>{s.title || "New conversation"}</strong>
                    <span>{new Date(s.updated_at).toLocaleString()}</span>
                  </button>
                  <button className="chat-icon-btn chat-history-archive" onClick={() => archive(s.id)} aria-label="Archive conversation"><Archive size={14} /></button>
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="chat-messages" ref={scrollRef}>
                {messages.length === 0 && (
                  <div className="chat-empty">
                    <Bot size={26} />
                    <strong>How can I help?</strong>
                    <span>{greetingText}</span>
                    <div className="chat-suggestions">
                      {(isPatient
                        ? ["I want to add an update", "Show my care plan status", "I have a question for my care team"]
                        : ["Show recent journeys", "Record a symptom update", "Re-evaluate a journey"]
                      ).map(s => (
                        <button key={s} className="chat-suggestion" onClick={() => send(s)}>{s}</button>
                      ))}
                    </div>
                    {error && <div className="chat-error">{error}</div>}
                  </div>
                )}
                {messages.map(m => (
                  <ChatMessageItem
                    key={m.id}
                    message={m}
                    busy={sending}
                    onConfirm={() => resolveAction(m.id, "confirm")}
                    onReject={() => resolveAction(m.id, "reject")}
                  />
                ))}
                {typing && (
                  <div className="chat-row chat-row--assistant">
 <div className="chat-avatar"><Bot size={13} /></div>
                    <div className="chat-bubble chat-bubble--assistant chat-bubble--typing"><i /><i /><i /></div>
                  </div>
                )}
              </div>

              <div className="chat-error-bar">{error}</div>

              <form className="chat-input-bar" onSubmit={(e) => { e.preventDefault(); send(); }}>
                {voiceSupported && (
                  <button type="button" className={`chat-mic ${listening ? "chat-mic--on" : ""}`} onClick={toggleVoice}
                    aria-label={listening ? "Stop listening" : "Speak your message"}>
                    {listening ? <MicOff size={17} /> : <Mic size={17} />}
                  </button>
                )}
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={listening ? "Listening… speak now" : "Type your message…"}
                  disabled={sending}
                  aria-label="Message"
                />
                <button className="chat-send" disabled={!input.trim() || sending} aria-label="Send message">
                  {sending ? <Loader2 size={16} className="chat-spin" /> : <Send size={16} />}
                </button>
              </form>
              <div className="chat-footnote">
                {isPatient
                  ? "Updates reach your care team for review — nothing changes your treatment directly."
                  : "Actions run only after you confirm them in this chat."}
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
