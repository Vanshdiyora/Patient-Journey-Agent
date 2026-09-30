import React, { useState } from "react";
import { Users } from "lucide-react";
import { Link } from "react-router-dom";
import { patientsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { useTabs } from "../../hooks/useTabs";
import { formatDate, initials } from "../../utils";
import { isAdmin, isCoordinator, portalName } from "../../utils/roles";
import { useAuth } from "../../context/AuthContext";
import { PageHeading, Panel, EmptyState, ErrorState, Pagination, SearchBox, SkeletonRows, TabBar } from "../../components";
import { TABS_BY_ROLE } from "./tabs";

export default function Patients() {
  const { user } = useAuth();
  const tabs = TABS_BY_ROLE[String(user?.role || "").toUpperCase()] || TABS_BY_ROLE.ADMIN;
  const { active: tab, select: setTab } = useTabs("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, loading, error } = useAsync(
    () => patientsApi.list({ search: search || undefined, filter: tab || undefined, limit, offset }),
    [search, offset, tab]
  );
  const patients = Array.isArray(data) ? data : data?.items || data?.patients || [];
  const activeTab = tabs.find(t => t.id === tab) || tabs[0];

  return <div>
    <PageHeading
      eyebrow={portalName(user)}
      title={isCoordinator(user) ? "Patient follow-ups" : "Patients"}
      description={isAdmin(user)
        ? "Full platform directory with operational slices."
        : isCoordinator(user)
          ? "Patients needing coordination follow-up."
          : "Find a patient and follow their care journey."}
    />
    <Panel>
      <TabBar tabs={tabs} active={tab} onChange={(id) => { setTab(id); setOffset(0); }} className="tab-bar--inset" />
      <div className="toolbar" style={{ borderTop: "1px solid var(--line)" }}>
        <SearchBox value={search} onChange={v => { setSearch(v); setOffset(0); }} placeholder="Search by name or patient reference…" />
        <span className="result-count">{activeTab?.label}</span>
      </div>
      {error ? <ErrorState error={error} title="Could not load patients" /> :
        loading ? <SkeletonRows /> :
          patients.length ? (
            <div className="table-wrap"><table>
              <thead><tr><th>Patient</th><th>Reference</th><th>Date of birth</th><th>Gender</th><th>Profile</th></tr></thead>
              <tbody>{patients.map(p => (
                <tr key={p.id}>
                  <td><div className="person-cell">
                    <div className="person-avatar">{initials(p.first_name, p.last_name)}</div>
                    <div><Link className="table-primary" to={`/patients/${p.id}`}>{p.first_name} {p.last_name}</Link><span>Patient record</span></div>
                  </div></td>
                  <td><code>{p.patient_reference}</code></td>
                  <td>{formatDate(p.date_of_birth)}</td>
                  <td>{p.gender || "—"}</td>
                  <td><Link className="table-link" to={`/patients/${p.id}`}>Open profile</Link></td>
                </tr>
              ))}</tbody>
            </table></div>
          ) : <EmptyState icon={Users} title="No patients here" text={`No patients match "${activeTab?.label}". Try another tab or clear the search.`} />}
      <Pagination offset={offset} limit={limit} count={patients.length} onPage={setOffset} />
    </Panel>
  </div>;
}
