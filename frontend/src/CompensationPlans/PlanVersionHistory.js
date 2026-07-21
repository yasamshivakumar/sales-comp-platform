import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";

function VersionBadge({ status }) {
  const tone =
    status === "Published"
      ? "published"
      : status === "Draft"
        ? "draft"
        : "archived";
  return <span className={`version-badge version-badge--${tone}`}>{status}</span>;
}

function formatRange(from, to) {
  if (!from) return "—";
  const end = to || "open-ended";
  return `${from} → ${end}`;
}

function PlanVersionHistory({ plan, onVersionsChanged }) {
  const { success, error } = useToast();
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [compareLeft, setCompareLeft] = useState("");
  const [compareRight, setCompareRight] = useState("");
  const [comparison, setComparison] = useState(null);
  const [quotasDraft, setQuotasDraft] = useState({});
  const [showArchived, setShowArchived] = useState(false);

  const loadVersions = useCallback(async () => {
    if (!plan?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`compensation-plans/${plan.id}/versions/`);
      setVersions(res.data || []);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load version history"));
    } finally {
      setLoading(false);
    }
  }, [plan?.id, error]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  const runAction = async (versionId, action, payload = {}) => {
    setBusyId(versionId);
    try {
      const res = await api.post(
        `compensation-plans/${plan.id}/versions/${versionId}/${action}/`,
        payload
      );
      const superseded = res.data.superseded_versions || [];
      if (action === "publish" && superseded.length > 0) {
        const summary = superseded
          .map(
            (s) =>
              `v${s.version_number} ${
                s.action === "archived"
                  ? "archived"
                  : `end-dated to ${s.effective_to}`
              }`
          )
          .join(", ");
        success(
          `Version ${res.data.version_number} published. Superseded: ${summary}.`
        );
      } else {
        success(`Version ${res.data.version_number} ${action}d.`);
      }
      await loadVersions();
      onVersionsChanged?.(res.data);
    } catch (err) {
      error(getApiErrorMessage(err, `Failed to ${action} version`));
    } finally {
      setBusyId(null);
    }
  };

  const saveQuotas = async (version) => {
    const text = quotasDraft[version.id];
    if (text == null) return;
    const rows = [];
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const [ym, amount, currency = ""] = trimmed.split(",").map((p) => p.trim());
      const [year, month] = (ym || "").split("-").map(Number);
      if (!year || !month || Number.isNaN(Number(amount))) {
        error(`Invalid quota line: "${trimmed}". Use YYYY-MM,amount[,currency]`);
        return;
      }
      rows.push({
        year,
        month,
        quota_amount: amount,
        currency,
      });
    }
    setBusyId(version.id);
    try {
      await api.patch(`compensation-plans/${plan.id}/versions/${version.id}/`, {
        quotas: rows,
      });
      success(`Quotas saved for version ${version.version_number}.`);
      await loadVersions();
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to save quotas"));
    } finally {
      setBusyId(null);
    }
  };

  const runCompare = async () => {
    if (!compareLeft || !compareRight) {
      error("Select two versions to compare.");
      return;
    }
    setBusyId("compare");
    try {
      const res = await api.get(
        `compensation-plans/${plan.id}/versions/compare/`,
        { params: { left: compareLeft, right: compareRight } }
      );
      setComparison(res.data);
    } catch (err) {
      error(getApiErrorMessage(err, "Version compare failed"));
    } finally {
      setBusyId(null);
    }
  };

  if (!plan?.id) return null;

  const archivedCount = versions.filter((v) => v.status === "Archived").length;
  const visibleVersions = showArchived
    ? versions
    : versions.filter((v) => v.status !== "Archived");

  return (
    <div className="panel plan-version-history cp-version-panel">
      <div className="plan-version-history__head">
        <h3 className="panel__title">Version history</h3>
        <button
          type="button"
          className="btn-secondary"
          onClick={loadVersions}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      {archivedCount > 0 ? (
        <label className="cp-switch">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          <span className="cp-switch__track">
            <span className="cp-switch__thumb" />
          </span>
          <span className="cp-switch__label">
            Show archived versions
            <span className="cp-switch__count">{archivedCount}</span>
          </span>
        </label>
      ) : null}

      {loading && versions.length === 0 ? (
        <p className="cp-loading">Loading versions…</p>
      ) : versions.length === 0 ? (
        <p className="cp-loading">No versions yet for this plan.</p>
      ) : visibleVersions.length === 0 ? (
        <p className="cp-loading">
          All {versions.length} versions are archived. Tick “Show archived
          versions” to see them.
        </p>
      ) : (
        <div className="cp-table-card" style={{ marginBottom: 16 }}>
        <div className="comp-plans-table-wrap">
          <table className="comp-plans-table enterprise-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Effective</th>
                <th>Table</th>
                <th>Rates</th>
                <th>Rules</th>
                <th>Quotas</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visibleVersions.map((version) => {
                const rateCount =
                  (version.sc_rate_tables?.length || 0) +
                  (version.sc_flat_rate_tables?.length || 0) +
                  (version.sc_lookup_tables?.length || 0);
                const quotaLines =
                  quotasDraft[version.id] ??
                  (version.quotas || [])
                    .map(
                      (q) =>
                        `${q.year}-${String(q.month).padStart(2, "0")},${q.quota_amount}${
                          q.currency ? `,${q.currency}` : ""
                        }`
                    )
                    .join("\n");
                return (
                  <tr key={version.id}>
                    <td>
                      <span className="cp-version-num">v{version.version_number}</span>
                      {version.created_from_version_number ? (
                        <div className="muted-mini">
                          from v{version.created_from_version_number}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <VersionBadge status={version.status} />
                    </td>
                    <td>{formatRange(version.effective_from, version.effective_to)}</td>
                    <td>{version.commission_table_type}</td>
                    <td>{rateCount}</td>
                    <td>{version.commission_rules?.length || 0}</td>
                    <td>
                      <textarea
                        className="quota-editor"
                        rows={2}
                        value={quotaLines}
                        disabled={version.status === "Archived" || busyId === version.id}
                        onChange={(e) =>
                          setQuotasDraft((prev) => ({
                            ...prev,
                            [version.id]: e.target.value,
                          }))
                        }
                        placeholder="2026-01,1000000,INR"
                      />
                      {version.status !== "Archived" ? (
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ marginTop: 6 }}
                          disabled={busyId === version.id}
                          onClick={() => saveQuotas(version)}
                        >
                          Save quotas
                        </button>
                      ) : null}
                    </td>
                    <td>
                      <div className="comp-plans-actions">
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={busyId === version.id}
                          onClick={() => runAction(version.id, "clone")}
                        >
                          Clone
                        </button>
                        {version.status === "Draft" ? (
                          <button
                            type="button"
                            className="btn-primary"
                            disabled={busyId === version.id}
                            onClick={() => runAction(version.id, "publish")}
                          >
                            Publish
                          </button>
                        ) : null}
                        {version.status === "Published" ? (
                          <button
                            type="button"
                            className="btn-secondary"
                            disabled={busyId === version.id}
                            onClick={() => runAction(version.id, "archive")}
                          >
                            Archive
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        </div>
      )}

      <div className="version-compare">
        <h4>Compare versions</h4>
        <div className="version-compare__controls">
          <select
            value={compareLeft}
            onChange={(e) => setCompareLeft(e.target.value)}
          >
            <option value="">Left version</option>
            {versions.map((v) => (
              <option key={`l-${v.id}`} value={v.id}>
                v{v.version_number} ({v.status})
              </option>
            ))}
          </select>
          <select
            value={compareRight}
            onChange={(e) => setCompareRight(e.target.value)}
          >
            <option value="">Right version</option>
            {versions.map((v) => (
              <option key={`r-${v.id}`} value={v.id}>
                v{v.version_number} ({v.status})
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-secondary"
            disabled={busyId === "compare"}
            onClick={runCompare}
          >
            Compare
          </button>
        </div>
        {comparison ? (
          <div className="version-compare__result">
            <p>
              Comparing v{comparison.left.version_number} → v
              {comparison.right.version_number}
            </p>
            {comparison.header_diff?.length ? (
              <ul>
                {comparison.header_diff.map((row) => (
                  <li key={row.field}>
                    <strong>{row.field}</strong>: {String(row.left)} →{" "}
                    {String(row.right)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-mini">No header field differences.</p>
            )}
            <pre className="version-compare__json">
              {JSON.stringify(
                {
                  rate_tables: comparison.rate_tables,
                  flat_rate_tables: comparison.flat_rate_tables,
                  lookup_tables: comparison.lookup_tables,
                  rules: comparison.rules,
                  quotas: comparison.quotas,
                },
                null,
                2
              )}
            </pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export { VersionBadge };
export default PlanVersionHistory;
