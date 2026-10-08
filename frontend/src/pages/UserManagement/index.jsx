import React, { useState } from "react";
import { ShieldCheck, UserCog } from "lucide-react";
import { adminApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { getErrorMessage, humanize, toList } from "../../utils";
import { useConfirm } from "../../components/ConfirmModal";
import { useToast } from "../../context/ToastContext";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, SkeletonRows, AlertBanner, Select, Pagination } from "../../components";
import { ROLES } from "../../utils/roles";

export default function UserManagement() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [offset, setOffset] = useState(0);
  const { data, loading, error } = useAsync(() => adminApi.users({ limit: 10, offset }), [refreshKey, offset]);
  const users = toList(data, "items", "users");
  const [saving, setSaving] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();

  const setRole = async (u, role) => {
    if (role === u.role) return;
    const ok = await confirm({
      title: `Change role to ${humanize(role)}?`,
      message: `${u.display_name || u.email} will immediately gain the permissions of the ${humanize(role)} role.`,
      confirmLabel: "Change role",
      intent: "primary",
    });
    if (!ok) {
      setRefreshKey(k => k + 1); // revert the Select to the stored role
      return;
    }
    await applyRole(u, role);
  };

  const applyRole = async (u, role) => {
    setSaving(u.id);
    try {
      await adminApi.setUserRole(u.id, { role });
      toast.success(`${u.display_name || u.email} is now ${humanize(role)}.`);
      setRefreshKey(k => k + 1);
    } catch (err) {
      toast.error(getErrorMessage(err));
      setRefreshKey(k => k + 1);
    } setSaving("");
  };

  const toggleActive = async (u) => {
    const ok = await confirm({
      title: u.is_active ? "Deactivate this account?" : "Reactivate this account?",
      message: u.is_active
        ? `${u.display_name || u.email} will immediately lose access to the workspace.`
        : `${u.display_name || u.email} will regain access to the workspace.`,
      confirmLabel: u.is_active ? "Deactivate" : "Reactivate",
      intent: u.is_active ? "danger" : "primary",
    });
    if (!ok) return;
    setSaving(u.id);
    try {
      await adminApi.setUserActive(u.id, { is_active: !u.is_active });
      toast.success(`${u.display_name || u.email} ${u.is_active ? "deactivated" : "reactivated"}.`);
      setRefreshKey(k => k + 1);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } setSaving("");
  };

  return <div>
    <PageHeading
      eyebrow="Administration"
      title="User management"
      description="Manage application identities, roles and activation status."
    />
    <Panel title="Application users" subtitle={`${data?.total ?? users.length} registered identities`} headerIcon={UserCog}>
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
                    <Select
                      value={u.role}
                      disabled={saving === u.id}
                      onChange={v => setRole(u, v)}
                      options={Object.values(ROLES).map(r => ({ value: r, label: humanize(r) }))}
                      className="role-select"
                    />
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
      {!loading && !error && <Pagination offset={offset} count={users.length} total={data?.total ?? 0} onPage={setOffset} />}
    </Panel>
    {confirmModal}
  </div>;
}
