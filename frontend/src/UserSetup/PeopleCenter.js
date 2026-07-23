import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import LoadingCenter from "../Components/LoadingCenter";
import PeopleDataGrid, { PeopleColumnPicker, usePeopleColumns } from "./PeopleDataGrid";

const PAGE_SIZE = 50;

const EMPTY_FILTERS = {
  q: "",
  role: "",
  department: "",
  business_group: "",
  region: "",
  territory: "",
  manager: "",
  plan: "",
  status: "",
  eligibility: "",
};

const SAVED_VIEWS = [
  { id: "all", label: "All Employees", params: {} },
  { id: "sales", label: "Sales Participants", params: { view: "sales" } },
  { id: "managers", label: "Managers", params: { view: "managers" } },
  { id: "pending", label: "Pending Activation", params: { view: "pending" } },
  { id: "plan_assigned", label: "Plan Assigned", params: { view: "plan_assigned" } },
  { id: "inactive", label: "Inactive Users", params: { view: "inactive" } },
];

const KPI_DEFS = [
  { key: "total_employees", label: "Total Employees", view: "all" },
  { key: "active_users", label: "Active Users", tone: "success" },
  { key: "pending_invitations", label: "Pending Invitations", tone: "warning", view: "pending" },
  { key: "inactive_users", label: "Inactive Users", view: "inactive" },
  { key: "admins", label: "Admins" },
  { key: "sales_participants", label: "Sales Participants", tone: "teal", view: "sales" },
];

function PeopleCenter() {
  const navigate = useNavigate();
  const { success, error } = useToast();
  const { visible, setVisible, columns } = usePeopleColumns();
  const [people, setPeople] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [viewId, setViewId] = useState("all");
  const [ordering, setOrdering] = useState("name");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [expandedId, setExpandedId] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const activeView = SAVED_VIEWS.find((v) => v.id === viewId) || SAVED_VIEWS[0];

  const queryParams = useMemo(() => {
    const params = { page, page_size: PAGE_SIZE, ordering };
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params[k] = v;
    });
    Object.entries(activeView.params || {}).forEach(([k, v]) => {
      if (v) params[k] = v;
    });
    return params;
  }, [filters, page, ordering, activeView]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [peopleRes, summaryRes] = await Promise.all([
        api.get("user-setup/", { params: queryParams }),
        api.get("user-setup/summary/"),
      ]);
      const data = peopleRes.data;
      const rows = Array.isArray(data) ? data : data?.results || [];
      setPeople(rows);
      setTotal(Array.isArray(data) ? rows.length : Number(data?.count || rows.length));
      setSummary(summaryRes.data);
      setSelectedIds(new Set());
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load people directory"));
      setPeople([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [queryParams, error]);

  useEffect(() => {
    const t = setTimeout(load, filters.q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, filters.q]);

  useEffect(() => {
    setPage(1);
  }, [viewId, filters, ordering]);

  const toggleAll = () => {
    if (people.length && people.every((p) => selectedIds.has(p.id))) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(people.map((p) => p.id)));
    }
  };

  const toggleOne = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const onSort = (key) => {
    setOrdering((prev) => {
      if (prev === key) return `-${key}`;
      if (prev === `-${key}`) return key;
      return key;
    });
  };

  const bulk = async (action, extra = {}) => {
    if (!selectedIds.size && action !== "export") return;
    if (!selectedIds.size) {
      error("Select at least one participant");
      return;
    }
    setBusy(true);
    try {
      const res = await api.post("user-setup/bulk/", {
        action,
        ids: Array.from(selectedIds),
        ...extra,
      });
      if (action === "export" && res.data?.csv) {
        const blob = new Blob([res.data.csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `participants-export-${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        success(`Exported ${res.data.count} participant(s)`);
      } else {
        success(`Updated ${res.data.updated} person(s)`);
        await load();
      }
    } catch (err) {
      error(getApiErrorMessage(err, "Bulk action failed"));
    } finally {
      setBusy(false);
    }
  };

  const filterCount = Object.entries(filters).filter(([k, v]) => k !== "q" && v).length;

  return (
    <div className="pe-console">
      <header className="pe-header">
        <div>
          <p className="pe-header__eyebrow">ICM Participant Management</p>
          <h1 className="pe-header__title">Compensation Participant Center</h1>
          <p className="pe-header__sub">
            Manage employees, compensation assignment, quota attainment, hierarchy, and access.
          </p>
        </div>
        <div className="pe-header__actions">
          <Link className="cp-btn-ghost" to="/user-setup/import">
            Upload Employees CSV
          </Link>
          <button type="button" className="btn-primary" onClick={() => navigate("/user-setup/new")}>
            + Create person
          </button>
        </div>
      </header>

      <section className="pe-kpis" aria-label="Summary">
        <div className="pe-kpis__grid">
          {KPI_DEFS.map((kpi) => {
            const raw = summary?.[kpi.key];
            const display = loading && !summary ? "—" : Number(raw || 0).toLocaleString();
            return (
              <button
                type="button"
                key={kpi.key}
                className={`pe-kpi${kpi.tone ? ` pe-kpi--${kpi.tone}` : ""}`}
                onClick={() => kpi.view && setViewId(kpi.view)}
              >
                <span className="pe-kpi__label">{kpi.label}</span>
                <span className="pe-kpi__value">{display}</span>
              </button>
            );
          })}
        </div>
      </section>

      <nav className="pe-views" aria-label="Saved views">
        {SAVED_VIEWS.map((view) => (
          <button
            key={view.id}
            type="button"
            className={`pe-views__btn${viewId === view.id ? " is-active" : ""}`}
            onClick={() => setViewId(view.id)}
          >
            {view.label}
          </button>
        ))}
      </nav>

      <div className="pe-toolbar">
        <input
          type="search"
          className="pe-toolbar__search"
          placeholder="Search name, email, employee ID, manager, territory, plan…"
          value={filters.q}
          onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))}
          aria-label="Search people"
        />
        <PeopleColumnPicker visible={visible} onChange={setVisible} />
        <button type="button" className="btn-secondary" onClick={() => setFilterOpen(true)}>
          Filters{filterCount ? ` (${filterCount})` : ""}
        </button>
        <button type="button" className="btn-secondary" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>

      {selectedIds.size > 0 ? (
        <div className="pe-bulk" role="toolbar">
          <span>{selectedIds.size} selected</span>
          <button
            type="button"
            className="btn-secondary"
            disabled={busy}
            onClick={() => {
              const planName = window.prompt("Assign plan (exact plan name):");
              if (planName) bulk("assign_plan", { plan_name: planName });
            }}
          >
            Assign Plan
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={busy}
            onClick={() => {
              const quota = window.prompt("Update quota (numeric target):");
              if (quota != null && quota !== "") bulk("update_quota", { quota });
            }}
          >
            Update Quota
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={busy}
            onClick={() => {
              const territory = window.prompt("Change territory (name or code):");
              if (territory) bulk("change_territory", { territory });
            }}
          >
            Change Territory
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => bulk("invite")}>
            Send Invitation
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => bulk("deactivate")}>
            Deactivate
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => bulk("export")}>
            Export
          </button>
          <button type="button" className="cp-btn-ghost" onClick={() => setSelectedIds(new Set())}>
            Clear
          </button>
        </div>
      ) : null}

      {loading && people.length === 0 ? (
        <LoadingCenter minHeight={220} />
      ) : (
        <PeopleDataGrid
          people={people}
          columns={columns}
          selectedIds={selectedIds}
          onToggleAll={toggleAll}
          onToggleOne={toggleOne}
          ordering={ordering}
          onSort={onSort}
          expandedId={expandedId}
          onExpand={setExpandedId}
          loading={loading}
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      )}

      {filterOpen ? (
        <div className="pe-filter-drawer" role="dialog" aria-modal="true">
          <button
            type="button"
            className="pe-filter-drawer__backdrop"
            aria-label="Close"
            onClick={() => setFilterOpen(false)}
          />
          <aside className="pe-filter-drawer__panel">
            <div className="pe-filter-drawer__head">
              <h2>Filters</h2>
              <button type="button" className="cp-btn-ghost" onClick={() => setFilterOpen(false)}>
                Close
              </button>
            </div>
            <div className="pe-filter-drawer__body">
              <label>
                Role
                <select
                  value={filters.role}
                  onChange={(e) => setFilters((p) => ({ ...p, role: e.target.value }))}
                >
                  <option value="">All</option>
                  <option value="Admin">Admin</option>
                  <option value="Finance">Finance</option>
                  <option value="Manager">Manager</option>
                  <option value="Sales Rep">Sales Rep</option>
                </select>
              </label>
              <label>
                Status
                <select
                  value={filters.status}
                  onChange={(e) => setFilters((p) => ({ ...p, status: e.target.value }))}
                >
                  <option value="">All</option>
                  <option value="active">Active</option>
                  <option value="plan_assigned">Plan Assigned</option>
                  <option value="pending_activation">Pending Activation</option>
                  <option value="invited">Invited</option>
                  <option value="suspended">Suspended</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
              <label>
                Department
                <input
                  value={filters.department}
                  onChange={(e) => setFilters((p) => ({ ...p, department: e.target.value }))}
                />
              </label>
              <label>
                Business Unit
                <input
                  value={filters.business_group}
                  onChange={(e) => setFilters((p) => ({ ...p, business_group: e.target.value }))}
                />
              </label>
              <label>
                Manager
                <input
                  value={filters.manager}
                  onChange={(e) => setFilters((p) => ({ ...p, manager: e.target.value }))}
                />
              </label>
              <label>
                Region
                <input
                  value={filters.region}
                  onChange={(e) => setFilters((p) => ({ ...p, region: e.target.value }))}
                />
              </label>
              <label>
                Territory
                <input
                  value={filters.territory}
                  onChange={(e) => setFilters((p) => ({ ...p, territory: e.target.value }))}
                />
              </label>
              <label>
                Compensation Plan
                <input
                  value={filters.plan}
                  onChange={(e) => setFilters((p) => ({ ...p, plan: e.target.value }))}
                />
              </label>
              <label>
                Eligibility
                <select
                  value={filters.eligibility}
                  onChange={(e) => setFilters((p) => ({ ...p, eligibility: e.target.value }))}
                >
                  <option value="">All</option>
                  <option value="eligible">Eligible</option>
                  <option value="not_eligible">Not Eligible</option>
                </select>
              </label>
            </div>
            <div className="pe-filter-drawer__foot">
              <button type="button" className="btn-secondary" onClick={() => setFilters(EMPTY_FILTERS)}>
                Clear
              </button>
              <button type="button" className="btn-primary" onClick={() => setFilterOpen(false)}>
                Apply
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export default PeopleCenter;
