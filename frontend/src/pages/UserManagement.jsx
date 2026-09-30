import React, { useState } from "react";
import { ShieldCheck, UserCog } from "lucide-react";
import { adminApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { getErrorMessage, humanize, toList } from "../utils/constants";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, SkeletonRows, AlertBanner } from "../components";
import { ROLES } from "../utils/roles";

export default function UserManagement() {
  const [refreshKey, setRefreshKey] = useState(0);
  const { data, loading, error } = useAsync(() => adminApi.users(), [refreshKey]);
  const users = toList(data, "items", "users");
  const [saving, setSaving] = useState("");
  const [feedback, setFeedback] = useState(null);

  const setRole = async (u, role) => {
    setSaving(u.id);
    setFeedback(null);
    try {
      await adminApi.setUserRole(u.id, { role });
      setFeedback({ tone: "success", text: `${u.display_name || u.email} is now ${humanize(role)}.` });
      setRefreshKey(k => k + 1);
    } catch (err) {
      setFeedback({ tone: "error", text: getErrorMessage(err) });
    } finally {
      setSaving("");
    }
  };

  const toggleActive = async (u) => {
    setSaving(u.id);
    setFeedback(null);
    try {
      await adminApi.setUserActive(u.id, { is_active: !u.is_active });
      setFeedback({ tone: "success", text: `${u.display_name || u.email} ${u.is_active ? "deactivated" : "reactivated"}.` });
      setRefreshKey(k => k + 1);
    } catch (err) {
      setFeedback({ color: "error", text: getErrorMessage(err) });
    } finally {
      setSaving("");
    }
  };

  return <div>
    <PageHeading
      eyebrow="Administration"
      title="User management"
      description="Manage application identities, roles and activation status."
    />
    <Panel title="Application users" subtitle={`${users.length} registered identities`} headerIcon={UserCog}>
      {feedback && <div style={{ padding: "0 18px" }}><AlertBanner tone={feedback.tone}>{feedback.text}</AlertBanner></div>}
      {error ? <ErrorState error={error} title="Could not load users" /> :
        loading ? <SkeletonRows /> :
          users.length ? (
            <div className="table-wrap"><table>
              <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>{users.map(u => (
                <tr key={u.id}>
                  <td><div className="person-cell">
                    <div className="person-avatar">{(u.display_name || u.email)[0].toUpperCase()}</div>
                    <div><span className="table-primary">{u.display_name || u.email}</span><span>{u.email}</span></div>
                  </div></td>
                  <td>
                    <select
                      value={u.role}
                      disabled={saving === u.id}
                      onChange={e => setRole(u, e.target.value)}
                      style={{ padding: "6px 8px", borderRadius: 7, border: "1px solid var(--line)", fontSize: 11 }}
                    >
                      {Object.values(ROLES).map(r => <option key={r} value={r}>{humanize(r)}</option>)}
                    </select>
                  </td>
                  <td><Badge kind="status" value={u.is_active ? "active" : "cancelled"} fallback={u.is_active ? "Active" : "Inactive"} /></td>
                  <td>
                    <button className="secondary-btn" disabled={saving === u.id} onClick={() => toggleActive(u)}>
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <EmptyState icon={ShieldCheck} title="No users" text="No identities are registered yet." />}
    </Panel>
  </div>;
}
