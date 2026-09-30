import React, { useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import { exceptionsApi } from "../../services";
import { useAsync } from "../../hooks/useAsync";
import { formatDate, getErrorMessage, humanize, severityClass, toList } from "../../utils";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, FilterSelect, ResultCount, SkeletonRows } from "../../components";
import { STATUS_OPTIONS, SEVERITY_OPTIONS } from "./filters";

export default function Exceptions() {
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [saving, setSaving] = useState("");
  const { data, loading, error } = useAsync(
    () => exceptionsApi.list({ status: status || undefined, severity: severity || undefined, limit: 100 }),
    [status, severity, refreshKey]
  );
  const rows = toList(data, "items", "exceptions");

  const resolve = async (e) => {
    setSaving(e.id);
    try {
      await exceptionsApi.update(e.id, { status: "resolved", recommended_action: e.recommended_action });
      setRefreshKey(x => x + 1);
    } catch (err) {
      alert(getErrorMessage(err));
    } finally {
      setSaving("");
    }
  };

  return <div>
    <PageHeading eyebrow="Operational exceptions" title="Exceptions" description="Identify blockers and close the issues that need care-team attention." />
    <Panel>
      <div className="toolbar">
        <div className="filter-group">
          <FilterSelect label="All statuses" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
          <FilterSelect label="All severity" value={severity} onChange={setSeverity} options={SEVERITY_OPTIONS} />
        </div>
        <ResultCount icon={AlertTriangle}>{rows.length} exceptions</ResultCount>
      </div>
      {error ? <ErrorState error={error} title="Could not load exceptions" /> :
        loading ? <SkeletonRows /> :
          rows.length ? (
            <div className="exception-list">{rows.map(e => (
              <article className="exception-card" key={e.id}>
                <div className={severityClass(e.severity)} />
                <div className="exception-main">
                  <div className="exception-top">
                    <div>
                      <span className={severityClass(e.severity)}>{humanize(e.severity)}</span>
                      <h3>{e.title}</h3>
                    </div>
                    <Badge kind="status" value={e.status} />
                  </div>
                  <p>{e.description}</p>
                  <div className="exception-meta">
                    <span>Created {formatDate(e.created_at, true)}</span>
                    <Link to={`/journeys/${e.journey_id}`}>View journey</Link>
                    {e.recommended_action && <span><strong>Recommended:</strong> {e.recommended_action}</span>}
                  </div>
                </div>
                {String(e.status).toLowerCase() !== "resolved" && (
                  <button className="secondary-btn" disabled={saving === e.id} onClick={() => resolve(e)}>
                    {saving === e.id ? "Resolving…" : <><CheckCircle2 size={16} /> Resolve</>}
                  </button>
                )}
              </article>
            ))}</div>
          ) : <EmptyState icon={CheckCircle2} title="No exceptions" text="No exceptions match the selected filters." />}
    </Panel>
  </div>;
}
