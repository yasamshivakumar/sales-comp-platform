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
        <>
        <ol className="cp-version-rail" aria-label="Version timeline">
          {visibleVersions.map((version) => (
            <li key={`rail-${version.id}`} className="cp-version-rail__item">
              <span className={`cp-version-rail__dot cp-version-rail__dot--${String(version.status).toLowerCase()}`} />
              <div>
                <strong>v{version.version_number}</strong>{" "}
                <VersionBadge status={version.status} />
                <p className="muted-mini">
                  {formatRange(version.effective_from, version.effective_to)}
                  {version.published_by_email ? ` · ${version.published_by_email}` : ""}
                </p>
              </div>
            </li>
          ))}
        </ol>
        <div className="cp-table-card" style={{ marginBottom: 16 }}>
        <div className="comp-plans-table-wrap">
          <table className="comp-plans-table enterprise-table">
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Effective</th>
                <th>Published by</th>
                <th>Reason / change</th>
                <th>Summary</th>
                <th>Rates</th>
                <th>Rules</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visibleVersions.map((version) => {
                const rateCount =
                  (version.sc_rate_tables?.length || 0) +
                  (version.sc_flat_rate_tables?.length || 0) +
                  (version.sc_lookup_tables?.length || 0);
                const ruleCount = version.commission_rules?.length || 0;
                const changeSummary = [
                  rateCount ? `${rateCount} rates` : null,
                  ruleCount ? `${ruleCount} rules` : null,
                  (version.quotas || []).length
                    ? `${version.quotas.length} quotas`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "No components";
                const reason =
                  version.description ||
                  (version.created_from_version_number
                    ? `Cloned from v${version.created_from_version_number}`
                    : version.status === "Published"
                      ? "Published for calculation"
                      : "Draft in progress");
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
                    <td>{version.published_by_email || "—"}</td>
                    <td>{reason}</td>
                    <td>{changeSummary}</td>
                    <td>{rateCount}</td>
                    <td>{ruleCount}</td>
                    <td>
                      <div className="comp-plans-actions">
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={busyId === version.id}
                          onClick={() => runAction(version.id, "clone")}
                        >
                          {version.status === "Published" || version.status === "Archived"
                            ? "Rollback / Clone"
                            : "Clone"}
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
        </>
      )}

      <div className="version-compare">
        <h4>Compare versions</h4>
        <div className="version-compare__controls">
          <select
            value={compareLeft}
            onChange={(e) => setCompareLeft(e.target.value)}
            aria-label="Left version"
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
            aria-label="Right version"
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
            {[
              ["rate_tables", "Rate tables"],
              ["flat_rate_tables", "Flat rates"],
              ["lookup_tables", "Lookup tables"],
              ["rules", "Rules"],
              ["quotas", "Quotas"],
            ].map(([key, label]) => {
              const block = comparison[key];
              if (!block) return null;
              const leftCount = Array.isArray(block.left)
                ? block.left.length
                : block.left
                  ? Object.keys(block.left).length
                  : 0;
              const rightCount = Array.isArray(block.right)
                ? block.right.length
                : block.right
                  ? Object.keys(block.right).length
                  : 0;
              const changed = JSON.stringify(block.left) !== JSON.stringify(block.right);
              return (
                <div key={key} className="version-compare__section">
                  <h5>
                    {label}{" "}
                    <span className="muted-mini">
                      ({leftCount} → {rightCount}
                      {changed ? " · changed" : " · identical"})
                    </span>
                  </h5>
                  {changed ? (
                    <div className="version-compare__cols">
                      <div>
                        <strong>Left</strong>
                        <ul>
                          {(Array.isArray(block.left) ? block.left : [block.left])
                            .filter(Boolean)
                            .slice(0, 12)
                            .map((row, idx) => (
                              <li key={`l-${key}-${idx}`}>
                                {typeof row === "object"
                                  ? Object.values(row).filter((v) => v != null && v !== "").slice(0, 4).join(" · ")
                                  : String(row)}
                              </li>
                            ))}
                        </ul>
                      </div>
                      <div>
                        <strong>Right</strong>
                        <ul>
                          {(Array.isArray(block.right) ? block.right : [block.right])
                            .filter(Boolean)
                            .slice(0, 12)
                            .map((row, idx) => (
                              <li key={`r-${key}-${idx}`}>
                                {typeof row === "object"
                                  ? Object.values(row).filter((v) => v != null && v !== "").slice(0, 4).join(" · ")
                                  : String(row)}
                              </li>
                            ))}
                        </ul>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export { VersionBadge };
export default PlanVersionHistory;
