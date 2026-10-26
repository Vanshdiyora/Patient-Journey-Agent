import { useCallback, useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../../context/AuthContext";
import { notificationsApi } from "../services/api";
import { formatDate, getErrorMessage } from "../../../utils";
import { buildPath, PATHS } from "../../../routes/paths";

export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const navigate = useNavigate();
  const { user } = useAuth();

  const refresh = useCallback(async () => {
    try {
      const result = await notificationsApi.list({ limit: 10, offset: 0 });
      setNotifications(result.items || []);
      setUnread(result.unread || 0);
      setError("");
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 60_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const openNotification = async (item) => {
    setBusyId(item.id);
    try {
      if (!item.read_at) await notificationsApi.markRead(item.id);
      setOpen(false);
      await refresh();
      if (user?.role === "PATIENT") {
        navigate(`${PATHS.myJourney}?journeyId=${encodeURIComponent(item.journey_id)}`);
      } else {
        navigate(buildPath(PATHS.journeyDetail, { journeyId: item.journey_id }));
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusyId("");
    }
  };

  return (
    <div className="notification-center">
      <button
        className="notification-trigger"
        type="button"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
      >
        <Bell size={19} />
        {unread > 0 && <span className="notification-count">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && <section className="notification-popover" aria-label="Notifications">
        <header className="notification-popover-head">
          <strong>Notifications</strong>
          <span>{unread ? `${unread} unread` : "All caught up"}</span>
        </header>
        {error && <p className="notification-error">Could not load or update notifications: {error}</p>}
        {!error && !notifications.length && <p className="notification-empty">You have no notifications.</p>}
        <div className="notification-list">
          {notifications.map(item => (
            <button
              className={`notification-item${item.read_at ? "" : " notification-item--unread"}`}
              key={item.id}
              type="button"
              disabled={!!busyId}
              onClick={() => openNotification(item)}
            >
              <span className="notification-item-head">
                <strong>{item.title}</strong>
                {!item.read_at && <i aria-label="Unread" />}
              </span>
              <span className="notification-item-body">{item.body}</span>
              <small>{formatDate(item.created_at, true)}</small>
            </button>
          ))}
        </div>
      </section>}
    </div>
  );
}
