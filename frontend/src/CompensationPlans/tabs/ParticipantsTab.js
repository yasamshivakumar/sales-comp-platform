import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import api, { getApiErrorMessage } from "../../api";
import { useToast } from "../../Components/Toast";
import LoadingCenter from "../../Components/LoadingCenter";
import { formatCoverageList, formatMoney } from "../compPlanUtils";

function ParticipantsTab() {
  const { plan } = useOutletContext();
  const { error, success } = useToast();
  const [q, setQ] = useState("");
  const [businessGroup, setBusinessGroup] = useState("");
  const [department, setDepartment] = useState("");
  const [region, setRegion] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(() => new Set());

  const load = useCallback(async () => {
    if (!plan?.id) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page_size: "50", page: String(page) });
      if (q.trim()) params.set("q", q.trim());
      if (businessGroup) params.set("business_group", businessGroup);
      if (department) params.set("department", department);
      if (region) params.set("region", region);
      const res = await api.get(`compensation-plans/${plan.id}/participants/?${params}`);
      setData(res.data);
      setSelected(new Set());
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load participants"));
    } finally {
      setLoading(false);
    }
  }, [plan?.id, q, businessGroup, department, region, page, error]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  useEffect(() => {
    setPage(1);
  }, [q, businessGroup, department, region]);

  const coverage = data?.coverage || plan.coverage || {};
  const totalPages = Math.max(1, Math.ceil((data?.count || 0) / (data?.page_size || 50)));

  const toggleRow = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!data?.results?.length) return;
    if (selected.size === data.results.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(data.results.map((r) => r.id)));
    }
  };

  const bulkHint = () => {
    success(
      `Selected ${selected.size} employee(s). Eligibility is driven by role/position — update Settings to change assignment.`
    );
  };

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <div className="cp-tab-panel__head">
          <div>
            <h2 className="panel__title">Participants</h2>
            <p className="cp-tab-lead">
              Employees matched by{" "}
              <strong>{data?.match === "position_name" ? "position name" : "role"}</strong>.
              Count: {data?.count ?? "—"}.
            </p>
          </div>
          <div className="cp-card__actions">
            <Link className="btn-secondary" to={`/comp-plans/${plan.id}/eligibility`}>
              Eligibility
            </Link>
            <Link className="btn-secondary" to={`/comp-plans/${plan.id}/settings`}>
              Assign via Settings
            </Link>
            <button
              type="button"
              className="btn-primary"
              disabled={!selected.size}
              onClick={bulkHint}
            >
              Bulk assignment ({selected.size})
            </button>
          </div>
        </div>

        <div className="cp-overview-grid" style={{ marginBottom: 14 }}>
          <div>
            <span className="cp-card__label">Departments</span>
            <span className="cp-card__value">{formatCoverageList(coverage.departments)}</span>
          </div>
          <div>
            <span className="cp-card__label">Regions</span>
            <span className="cp-card__value">{formatCoverageList(coverage.regions)}</span>
          </div>
          <div>
            <span className="cp-card__label">Business units</span>
            <span className="cp-card__value">{formatCoverageList(coverage.business_units)}</span>
          </div>
        </div>

        <div className="cp-catalog-toolbar" role="search">
          <label className="cp-catalog-toolbar__search">
            <span className="visually-hidden">Search participants</span>
            <input
              type="search"
              placeholder="Search name, email, employee id, department, manager…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </label>
          <select
            aria-label="Business unit"
            value={businessGroup}
            onChange={(e) => setBusinessGroup(e.target.value)}
          >
            <option value="">All business units</option>
            {(coverage.business_units || []).map((bg) => (
              <option key={bg} value={bg}>
                {bg}
              </option>
            ))}
          </select>
          <select
            aria-label="Department"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          >
            <option value="">All departments</option>
            {(coverage.departments || []).map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <select
            aria-label="Region"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
          >
            <option value="">All regions</option>
            {(coverage.regions || []).map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>

        {loading && !data ? (
          <LoadingCenter minHeight={160} />
        ) : !data?.results?.length ? (
          <div className="cp-empty-inline">
            <p>No matching employees found</p>
            <p className="cp-tab-lead">Adjust eligibility in Settings or clear filters.</p>
          </div>
        ) : (
          <>
            <div className="enterprise-table-wrap">
              <table className="enterprise-table">
                <thead>
                  <tr>
                    <th>
                      <input
                        type="checkbox"
                        aria-label="Select all on page"
                        checked={
                          data.results.length > 0 && selected.size === data.results.length
                        }
                        onChange={toggleAll}
                      />
                    </th>
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Region</th>
                    <th>Manager</th>
                    <th>Position</th>
                    <th>Current quota</th>
                    <th>Current attainment</th>
                    <th>Current commission</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Select ${row.name}`}
                          checked={selected.has(row.id)}
                          onChange={() => toggleRow(row.id)}
                        />
                      </td>
                      <td>
                        <strong>{row.name || "—"}</strong>
                        <div className="muted-mini">{row.email}</div>
                      </td>
                      <td>{row.department || "—"}</td>
                      <td>{row.region || "—"}</td>
                      <td>{row.manager || "—"}</td>
                      <td>{row.position_name || "—"}</td>
                      <td>{formatMoney(row.current_quota)}</td>
                      <td>
                        {row.current_attainment == null
                          ? "—"
                          : `${row.current_attainment}%`}
                      </td>
                      <td>{formatMoney(row.current_commission)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.count > data.page_size ? (
              <div className="cp-pagination">
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <span className="cp-pagination__meta">
                  Page {page} of {totalPages} · {data.count} employees
                </span>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}

export default ParticipantsTab;
