import React, { useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import { exceptionsApi } from "../../../services/index";
import { useAsync } from "../../../hooks/useAsync";
import { formatDate, getErrorMessage, humanize, severityClass, toList } from "../../../utils/index";
import { PageHeading, Panel, EmptyState, ErrorState, Badge, FilterSelect, ResultCount, SkeletonRows, Pagination } from "../../../components/index";
import { useConfirm } from "../../../components/ConfirmModal";
import { useToast } from "../../../context/ToastContext";
import { STATUS_OPTIONS, SEVERITY_OPTIONS } from "./filters";

export default function Exceptions() {
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [offset, setOffset] = useState(0);
  const [saving, setSaving] = useState("");
  const [confirm, confirmModal] = useConfirm();
  const toast = useToast();
  const { data, loading, error } = useAsync(
    () => exceptionsApi.list({ status: status || undefined, severity: severity || undefined, limit: 10, offset }),
    [status, severity, offset, refreshKey]
  );
  const rows = toList(data, "items", "exceptions");

  const resolve = async (e) => {
    const ok = await confirm({
      title: "Resolve this exception?",
      message: e.title || "The exception will be marked resolved for the care team.",
      confirmLabel: "Resolve",
      intent: "primary",
    });
    if (!ok) return;
    setSaving(e.id);
    try {
      await exceptionsApi.update(e.id, { status: "resolved", recommended_action: e.recommended_action });
      toast.success("Exception resolved.");
      if (rows.length === 1 && offset > 0 && status && !status.toLowerCase().includes("resolved")) setOffset(offset - 10);
      else setRefreshKey(x => x + 1);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving("");
    }
  };

  return <div>
    <PageHeading eyebrow="Operational exceptions" title="Exceptions" description="Identify blockers and close the issues that need care-team attention." />
    <Panel>
      <div className="toolbar">
        <div className="filter-group">
          <FilterSelect label="All statuses" value={status} onChange={v => { setStatus(v); setOffset(0); }} options={STATUS_OPTIONS} />
          <FilterSelect label="All severity" value={severity} onChange={v => { setSeverity(v); setOffset(0); }} options={SEVERITY_OPTIONS} />
        </div>
        <ResultCount icon={AlertTriangle}>{data?.total ?? rows.length} exceptions</ResultCount>
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
      {!loading && !error && <Pagination offset={offset} count={rows.length} total={data?.total ?? 0} onPage={setOffset} />}
    </Panel>
    {confirmModal}
  </div>;
}
