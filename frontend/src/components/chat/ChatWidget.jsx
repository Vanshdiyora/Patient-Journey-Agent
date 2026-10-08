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

function mergeMessages(current, incoming) {
  const rows = [...current];
  for (const message of incoming.filter(Boolean)) {
    const index = rows.findIndex(row => row.id === message.id);
    if (index >= 0) rows[index] = message;
    else rows.push(message);
  }
  return rows;
}

function waitForOpen(socket) {
  if (socket.readyState === WebSocket.OPEN) return Promise.resolve(socket);
  if (socket.readyState !== WebSocket.CONNECTING) return Promise.reject(new Error("Chat connection is unavailable."));
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      clearTimeout(timer);
      socket.removeEventListener("open", onOpen);
      socket.removeEventListener("error", onFailure);
      socket.removeEventListener("close", onFailure);
    };
    const onOpen = () => { cleanup(); resolve(socket); };
    const onFailure = () => { cleanup(); reject(new Error("Could not connect to chat. Please try again.")); };
    const timer = setTimeout(() => { cleanup(); socket.close(); reject(new Error("Chat connection timed out.")); }, 10000);
    socket.addEventListener("open", onOpen);
    socket.addEventListener("error", onFailure);
    socket.addEventListener("close", onFailure);
  });
}

function socketRequest(socket, payload, onTyping) {
  const requestId = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      clearTimeout(timer);
      socket.removeEventListener("message", onMessage);
      socket.removeEventListener("close", onClose);
      socket.removeEventListener("error", onClose);
    };
    const onMessage = event => {
      let frame;
      try { frame = JSON.parse(event.data); } catch { return; }
      if (frame.request_id !== requestId && !(frame.type === "error" && !frame.request_id)) return;
      if (frame.type === "typing") { onTyping?.(); return; }
      if (frame.type === "message" || frame.type === "action") { cleanup(); resolve(frame); }
      if (frame.type === "error") { cleanup(); reject(new Error(frame.detail || "Chat request failed.")); }
    };
    const onClose = () => { cleanup(); reject(new Error("Chat connection closed while processing. Check history before retrying.")); };
    const timer = setTimeout(() => { cleanup(); reject(new Error("Chat response timed out. Check history before retrying.")); }, 610000);
    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onClose);
    try { socket.send(JSON.stringify({ ...payload, request_id: requestId })); }
    catch (error) { cleanup(); reject(error); }
  });
}

/**
 * Floating assistant available in every portal. Chat turns and action
 * decisions use the WebSocket. All role scoping
 * is enforced server-side — the UI only mirrors it (e.g. patient-safe
 * actions, staff-only orchestration surfaces).
 */
export default function ChatWidget() {
  const { user, token } = useAuth();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState("chat"); // chat | history
  const [sessions, setSessions] = useState([]);
  const [sessionOffset, setSessionOffset] = useState(0);
  const [sessionTotal, setSessionTotal] = useState(0);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [sessionsError, setSessionsError] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messageOffset, setMessageOffset] = useState(0);
  const [messageTotal, setMessageTotal] = useState(0);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [historyLoadError, setHistoryLoadError] = useState("");
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
  const sendingRef = useRef(false);
  const recognitionRef = useRef(null);
  const sessionRef = useRef(null);
  const historyRequestRef = useRef(0);
  const messageRequestRef = useRef(0);

  const isPatient = user?.role?.toUpperCase() === "PATIENT";

  // ------------------------------------------------------------------ data

  const loadSessions = useCallback((offset = 0) => {
    const request = ++historyRequestRef.current;
    setSessionOffset(offset);
    setLoadingSessions(true);
    setSessionsError("");
    chatApi.listSessions({ limit: 10, offset })
      .then(r => { if (request === historyRequestRef.current) { setSessions(r.items || []); setSessionTotal(r.total || 0); } })
      .catch(() => { if (request === historyRequestRef.current) setSessionsError("Could not load conversations."); })
      .finally(() => { if (request === historyRequestRef.current) setLoadingSessions(false); });
  }, []);

  const loadMessages = useCallback((id, offset = 0) => {
    if (!id) return;
    const request = ++messageRequestRef.current;
    setMessageOffset(offset);
    setLoadingMessages(true);
    setHistoryLoadError("");
    chatApi.messages(id, { limit: 10, offset })
      .then(r => {
        if (request === messageRequestRef.current && sessionRef.current === id) {
          setMessages(r.items || []);
          setMessageTotal(r.total || 0);
        }
      })
      .catch(() => { if (request === messageRequestRef.current && sessionRef.current === id) setHistoryLoadError("Could not load this conversation."); })
      .finally(() => { if (request === messageRequestRef.current) setLoadingMessages(false); });
  }, []);

  const startNewChat = useCallback(() => {
    if (sendingRef.current) return;
    messageRequestRef.current += 1;
    sessionRef.current = null;
    setSessionId(null);
    setMessages([]);
    setMessageOffset(0);
    setMessageTotal(0);
    setLoadingMessages(false);
    setHistoryLoadError("");
    setView("chat");
    setError("");
  }, []);

  const openSession = useCallback((id) => {
    if (sendingRef.current) return;
    sessionRef.current = id;
    setSessionId(id);
    setMessages([]);
    setMessageOffset(0);
    setError("");
    loadMessages(id);
    setView("chat");
  }, [loadMessages]);

  useEffect(() => {
    if (open) loadSessions(0);
  }, [open, loadSessions]);

  // Scroll to bottom on new messages/typing state.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, typing, open]);

  // ------------------------------------------------------------ websocket

  const ensureSocket = useCallback(async () => {
    let socket = socketRef.current;
    if (!socket || socket.readyState === WebSocket.CLOSING || socket.readyState === WebSocket.CLOSED) {
      socket = openChatSocket(token);
      socketRef.current = socket;
      socket.addEventListener("close", () => {
        if (socketRef.current === socket) socketRef.current = null;
      });
    }
    return waitForOpen(socket);
  }, [token]);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || sendingRef.current || loadingMessages || historyLoadError) return;
    sendingRef.current = true;
    setError("");
    setInput("");
    const localId = `local-${crypto.randomUUID()}`;
    setMessages(prev => [...prev, {
      id: localId, session_id: sessionRef.current, role: "user",
      content, meta: null, created_at: new Date().toISOString(),
    }]);
    setSending(true);
    setTyping(true);
    let sid = sessionRef.current;
    let requestStarted = false;
    try {
      const socket = await ensureSocket();
      if (!sid) {
        const created = await chatApi.createSession();
        sid = created.id;
        sessionRef.current = sid;
        setSessionId(sid);
      }
      requestStarted = true;
      const result = await socketRequest(socket, { type: "message", session_id: sid, content }, () => {
        if (sessionRef.current === sid) setTyping(true);
      });
      if (sessionRef.current === sid) {
        setMessages(prev => mergeMessages(prev.filter(m => m.id !== localId), [result.user_message, result.assistant_message]));
        loadMessages(sid, 0);
      }
      loadSessions(0);
    } catch (err) {
      setError(getErrorMessage(err));
      setMessages(prev => prev.filter(m => m.id !== localId));
      if (!requestStarted && sessionRef.current === sid) setInput(content);
    } finally {
      sendingRef.current = false;
      setSending(false);
      setTyping(false);
    }
  };

  // ------------------------------------------------------- action confirm

  const resolveAction = async (messageId, action) => {
    if (!sessionRef.current || !messageId || sendingRef.current) return;
    const sid = sessionRef.current;
    sendingRef.current = true;
    setSending(true);
    setTyping(true);
    try {
      const socket = await ensureSocket();
      const result = await socketRequest(socket, { type: action, session_id: sid, message_id: messageId });
      if (sessionRef.current === sid) {
        setMessages(prev => mergeMessages(prev.map(m => m.id === messageId ? result.message : m), [result.result_message]));
        loadMessages(sid, 0);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      sendingRef.current = false;
      setSending(false);
      setTyping(false);
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
      setSessionTotal(prev => Math.max(0, prev - 1));
      if (sessions.length === 1 && sessionOffset > 0) loadSessions(sessionOffset - 10);
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
                <button className="chat-icon-btn" disabled={sending} onClick={startNewChat} aria-label="New conversation" title="New conversation"><Plus size={17} /></button>
                <button className="chat-icon-btn" disabled={sending} onClick={() => { loadSessions(0); setView("history"); }} aria-label="History" title="History"><Archive size={17} /></button>
              </>
            )}
            <button className="chat-icon-btn" onClick={() => setOpen(false)} aria-label="Close assistant"><X size={17} /></button>
          </div>

          {view === "history" ? (
            <div className="chat-history-list">
              {loadingSessions && <div className="chat-loading" role="status"><Loader2 size={17} className="chat-spin" /> Loading conversations…</div>}
              {!loadingSessions && sessionsError && <div className="chat-load-error" role="alert">{sessionsError}<button type="button" onClick={() => loadSessions(sessionOffset)}>Retry</button></div>}
              {!loadingSessions && !sessionsError && sessions.length === 0 && <div className="chat-empty">No conversations yet.</div>}
              {sessions.map(s => (
                <div key={s.id} className={`chat-history-item ${s.id === sessionId ? "chat-history-item--active" : ""}`}>
                  <button className="chat-history-main" onClick={() => openSession(s.id)}>
                    <strong>{s.title || "New conversation"}</strong>
                    <span>{new Date(s.updated_at).toLocaleString()}</span>
                  </button>
                  <button className="chat-icon-btn chat-history-archive" onClick={() => archive(s.id)} aria-label="Archive conversation"><Archive size={14} /></button>
                </div>
              ))}
              {!loadingSessions && !sessionsError && <div className="chat-history-pagination">
                <button type="button" disabled={sessionOffset === 0} onClick={() => loadSessions(Math.max(0, sessionOffset - 10))}>Newer</button>
                <span>Page {Math.floor(sessionOffset / 10) + 1} of {Math.max(1, Math.ceil(sessionTotal / 10))}</span>
                <button type="button" disabled={sessionOffset + sessions.length >= sessionTotal} onClick={() => loadSessions(sessionOffset + 10)}>Older</button>
              </div>}
            </div>
          ) : (
            <>
              <div className="chat-messages" ref={scrollRef}>
                {sessionId && !loadingMessages && !historyLoadError && <div className="chat-history-pagination">
                  <button type="button" disabled={messageOffset + 10 >= messageTotal} onClick={() => loadMessages(sessionId, messageOffset + 10)}>Older</button>
                  <span>Page {Math.floor(messageOffset / 10) + 1} of {Math.max(1, Math.ceil(messageTotal / 10))}</span>
                  <button type="button" disabled={messageOffset === 0} onClick={() => loadMessages(sessionId, Math.max(0, messageOffset - 10))}>Newer</button>
                </div>}
                {loadingMessages && <div className="chat-loading chat-loading--messages" role="status"><Loader2 size={19} className="chat-spin" /> Loading conversation…</div>}
                {!loadingMessages && historyLoadError && <div className="chat-load-error" role="alert">{historyLoadError}<button type="button" onClick={() => loadMessages(sessionId, messageOffset)}>Retry</button></div>}
                {!loadingMessages && !historyLoadError && messages.length === 0 && (
                  <div className="chat-empty">
                    <Bot size={26} />
                    <strong>How can I help?</strong>
                    <span>{greetingText}</span>
                    <div className="chat-suggestions">
                      {(isPatient
                        ? ["I want to add an update", "Show my care plan status", "I have a question for my care team"]
                        : ["Show recent journeys", "Start the knee pathway for a patient", "What tasks are pending?"]
                      ).map(s => (
                        <button key={s} className="chat-suggestion" onClick={() => send(s)}>{s}</button>
                      ))}
                    </div>
                    {error && <div className="chat-error">{error}</div>}
                  </div>
                )}
                {!loadingMessages && messages.slice(-10).map(m => (
                  <ChatMessageItem
                    key={m.id}
                    message={m}
                    user={user}
                    onNavigate={() => setOpen(false)}
                    busy={sending}
                    onConfirm={() => resolveAction(m.id, "confirm")}
                    onReject={() => resolveAction(m.id, "reject")}
                  />
                ))}
                {!loadingMessages && typing && (
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
                  disabled={sending || loadingMessages || Boolean(historyLoadError)}
                  aria-label="Message"
                />
                <button className="chat-send" disabled={!input.trim() || sending || loadingMessages || Boolean(historyLoadError)} aria-label="Send message">
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
