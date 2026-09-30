import React, { useState } from "react";
import { Users } from "lucide-react";
import { Link } from "react-router-dom";
import { patientsApi } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { formatDate, initials } from "../utils/constants";
import { PageHeading, Panel, EmptyState, ErrorState, Pagination, SearchBox, SkeletonRows } from "../components";

export default function Patients() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, loading, error } = useAsync(() => patientsApi.list({ search: search || undefined, limit, offset }), [search, offset]);
  const patients = Array.isArray(data) ? data : data?.items || data?.patients || [];

  return <div>
    <PageHeading eyebrow="Patient directory" title="Patients" description="Find a patient and follow their care journey." />
    <Panel>
      <div className="toolbar">
        <SearchBox value={search} onChange={v => { setSearch(v); setOffset(0); }} placeholder="Search by name or patient reference…" />
        <button className="secondary-btn">Filters</button>
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
          ) : <EmptyState icon={Users} title="No patients found" text="Try another patient name or reference." />}
      <Pagination offset={offset} limit={limit} count={patients.length} onPage={setOffset} />
    </Panel>
  </div>;
}
