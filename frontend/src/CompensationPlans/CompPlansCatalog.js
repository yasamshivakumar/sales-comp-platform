import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import CompPlansKpis from "./CompPlansKpis";
import CompPlansActionCenter from "./CompPlansActionCenter";
import CompPlansFilterDrawer from "./CompPlansFilterDrawer";
import CompPlansDataGrid from "./CompPlansDataGrid";
import LoadingCenter from "../Components/LoadingCenter";
import { normalizePlansResponse } from "./compPlanUtils";

const EMPTY_FILTERS = {
  q: "",
  version_status: "",
  status: "",
  role: "",
  business_group: "",
  health: "",
  commission_table_type: "",
  effective_on: "",
  plan_type: "",
  owner: "",
  approver: "",
  calculation_status: "",
  approval_status: "",
  readiness_min: "",
  employees_min: "",
};

const PAGE_SIZE = 50;

function activeFilterCount(filters) {
  return Object.entries(filters).filter(([key, value]) => {
    if (key === "q") return false;
    return value !== "" && value != null;
  }).length;
}

function CompPlansCatalog() {
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [plans, setPlans] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [expandedId, setExpandedId] = useState(null);
  const [focusPlanIds, setFocusPlanIds] = useState(null);
  const [actionBanner, setActionBanner] = useState(null);
  const [globalHits, setGlobalHits] = useState([]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (key === "employees_min") return;
      if (value !== "" && value != null) params.set(key, value);
    });
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));
    return params.toString();
  }, [filters, page]);

  const fetchCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const [plansRes, summaryRes] = await Promise.all([
        api.get(`compensation-plans/?${queryString}`),
        api.get("compensation-plans/summary/"),
      ]);
      const normalized = normalizePlansResponse(plansRes.data);
      let rows = normalized.results;
      const minEmp = Number(filters.employees_min);
      if (!Number.isNaN(minEmp) && filters.employees_min !== "") {
        rows = rows.filter((p) => {
          const n = p.participant_count ?? p.coverage?.employees_assigned ?? 0;
          return Number(n) >= minEmp;
        });
      }
      if (focusPlanIds?.size) {
        rows = [...rows].sort((a, b) => {
          const af = focusPlanIds.has(a.id) ? 0 : 1;
          const bf = focusPlanIds.has(b.id) ? 0 : 1;
          return af - bf;
        });
      }
      setPlans(rows);
      setTotal(normalized.count ?? normalized.results.length);
      setSummary(summaryRes.data);
      setSelectedIds(new Set());
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load compensation plans"));
    } finally {
      setLoading(false);
    }
  }, [queryString, error, filters.employees_min, focusPlanIds]);

  useEffect(() => {
    const handle = setTimeout(fetchCatalog, filters.q ? 250 : 0);
    return () => clearTimeout(handle);
  }, [fetchCatalog, filters.q]);

  useEffect(() => {
    if (!filters.q || filters.q.trim().length < 2) {
      setGlobalHits([]);
      return undefined;
    }
    const handle = setTimeout(async () => {
      try {
        const res = await api.get(
          `compensation-plans/search/?q=${encodeURIComponent(filters.q.trim())}`
        );
        setGlobalHits(res.data?.results || []);
      } catch {
        setGlobalHits([]);
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [filters.q]);

  useEffect(() => {
    setPage(1);
  }, [
    filters.q,
    filters.version_status,
    filters.status,
    filters.role,
    filters.business_group,
    filters.health,
    filters.commission_table_type,
    filters.effective_on,
    filters.plan_type,
    filters.owner,
    filters.approver,
    filters.calculation_status,
    filters.approval_status,
    filters.readiness_min,
    filters.employees_min,
  ]);

  const roles = useMemo(() => {
    const set = new Set();
    plans.forEach((plan) => {
      if (plan.role) set.add(plan.role);
    });
    return Array.from(set).sort();
  }, [plans]);

  const businessGroups = useMemo(() => {
    const set = new Set();
    plans.forEach((plan) => {
      if (plan.business_group) set.add(plan.business_group);
    });
    return Array.from(set).sort();
  }, [plans]);

  const owners = useMemo(() => {
    const set = new Set();
    plans.forEach((plan) => {
      if (plan.owner) set.add(plan.owner);
    });
    return Array.from(set).sort();
  }, [plans]);

  const approvers = useMemo(() => {
    const set = new Set();
    plans.forEach((plan) => {
      if (plan.approver) set.add(plan.approver);
    });
    return Array.from(set).sort();
  }, [plans]);

  const setHealthFilter = (health) => {
    setFocusPlanIds(null);
    setActionBanner(null);
    setFilters((prev) => ({ ...prev, health, calculation_status: "" }));
  };

  const setCalcFilter = (calculation_status) => {
    setFocusPlanIds(null);
    setActionBanner(null);
    setFilters((prev) => ({ ...prev, calculation_status, health: "" }));
  };

  const resolveAction = (item) => {
    const ids = new Set(item.plan_ids || []);
    setFocusPlanIds(ids.size ? ids : null);
    setActionBanner(item.title);
    setExpandedId(null);
    if (item.code === "expires_soon") {
      setFilters((prev) => ({
        ...prev,
        health: "attention",
        calculation_status: "",
      }));
    } else {
      setFilters((prev) => ({
        ...prev,
        calculation_status: "blocked",
        health: "",
      }));
    }
    document.getElementById("cp-plan-grid")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const clonePlan = async (plan) => {
    const versionId = plan.current_version?.id;
    if (!versionId) return;
    setBusyId(plan.id);
    try {
      await api.post(`compensation-plans/${plan.id}/versions/${versionId}/clone/`);
      success(`Cloned version for ${plan.plan_name}.`);
      await fetchCatalog();
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to clone version"));
    } finally {
      setBusyId(null);
    }
  };

  const archivePlan = async (plan) => {
    const versionId = plan.current_version?.id;
    if (!versionId) return;
    setBusyId(plan.id);
    try {
      await api.post(`compensation-plans/${plan.id}/versions/${versionId}/archive/`);
      success(`Archived current version of ${plan.plan_name}.`);
      await fetchCatalog();
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to archive version"));
    } finally {
      setBusyId(null);
    }
  };

  const bulkArchive = async (ids) => {
    const selected = plans.filter((p) => ids.has(p.id));
    for (const plan of selected) {
      // Sequential to avoid overloading API
      // eslint-disable-next-line no-await-in-loop
      await archivePlan(plan);
    }
  };

  const bulkExport = (ids) => {
    const selected = plans.filter((p) => ids.has(p.id));
    const header = [
      "Plan Name",
      "Type",
      "Role",
      "Business Unit",
      "Status",
      "Health Score",
      "Calculation",
      "Employees",
      "Owner",
    ];
    const lines = selected.map((p) =>
      [
        p.plan_name,
        p.plan_type_label || p.plan_type || "",
        p.role || "",
        p.business_group || "",
        p.current_version?.status || p.status || "",
        p.health?.score ?? "",
        p.calculation_status?.status || "",
        p.participant_count ?? "",
        p.owner || "",
      ]
        .map((cell) => `"${String(cell).replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "compensation-plans.csv";
    a.click();
    URL.revokeObjectURL(url);
    success(`Exported ${selected.length} plan${selected.length === 1 ? "" : "s"}.`);
  };

  const bulkCompare = (ids) => {
    const list = Array.from(ids);
    if (list.length < 1) return;
    navigate(`/comp-plans/${list[0]}/versions`);
  };

  const bulkSimulate = (ids) => {
    const first = plans.find((p) => ids.has(p.id));
    if (first) navigate(`/comp-plans/${first.id}/simulation`);
  };

  const filterCount = activeFilterCount(filters);

  return (
    <div className="cp-module cp-ops-console">
      <header className="cp-ops-header">
        <div>
          <p className="cp-ops-header__eyebrow">Compensation</p>
          <h1 className="cp-ops-header__title">Compensation Operations Center</h1>
          <p className="cp-ops-header__sub">
            Manage compensation plans, monitor readiness, and resolve payout risks.
          </p>
        </div>
        <div className="cp-ops-header__actions">
          <Link className="cp-btn-ghost" to="/comp-plans/ai">
            AI Plan Builder
          </Link>
          <button type="button" className="btn-primary" onClick={() => navigate("/comp-plans/new")}>
            + New plan
          </button>
        </div>
      </header>

      <CompPlansKpis
        summary={summary}
        loading={loading && !summary}
        onFilterHealth={setHealthFilter}
        onFilterCalc={setCalcFilter}
      />

      <CompPlansActionCenter
        summary={summary}
        loading={loading && !summary}
        onResolve={resolveAction}
      />

      <div className="cp-ops-toolbar" id="cp-plan-grid">
        <div className="cp-ops-toolbar__search">
          <input
            type="search"
            placeholder="Search plans, owners, roles…"
            value={filters.q}
            onChange={(e) => setFilters((prev) => ({ ...prev, q: e.target.value }))}
            aria-label="Search plans"
          />
        </div>
        <button type="button" className="btn-secondary" onClick={() => setFilterOpen(true)}>
          Filters{filterCount ? ` (${filterCount})` : ""}
        </button>
        {actionBanner || filterCount ? (
          <button
            type="button"
            className="cp-btn-ghost"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setFocusPlanIds(null);
              setActionBanner(null);
            }}
          >
            Clear
          </button>
        ) : null}
      </div>

      {actionBanner ? (
        <div className="cp-ops-banner" role="status">
          Showing plans related to: <strong>{actionBanner}</strong>
          <button
            type="button"
            className="cp-btn-ghost"
            onClick={() => {
              setActionBanner(null);
              setFocusPlanIds(null);
            }}
          >
            Dismiss
          </button>
        </div>
      ) : null}

      {globalHits.length > 0 ? (
        <div className="cp-global-search" role="region" aria-label="Search results">
          <ul className="cp-global-search__list">
            {globalHits.slice(0, 8).map((hit) => (
              <li key={`${hit.type}-${hit.id}`}>
                <button
                  type="button"
                  className="cp-global-search__hit"
                  onClick={() => navigate(hit.href)}
                >
                  <span className="cp-global-search__type">{hit.type}</span>
                  <strong>{hit.label}</strong>
                  <span className="muted-mini">{hit.meta}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {loading && plans.length === 0 ? (
        <LoadingCenter minHeight={240} />
      ) : (
        <CompPlansDataGrid
          plans={plans}
          loading={loading}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          expandedId={expandedId}
          onExpand={setExpandedId}
          busyId={busyId}
          onClone={clonePlan}
          onArchive={archivePlan}
          focusPlanIds={focusPlanIds}
          onBulkArchive={bulkArchive}
          onBulkExport={bulkExport}
          onBulkCompare={bulkCompare}
          onBulkSimulate={bulkSimulate}
        />
      )}

      <CompPlansFilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(EMPTY_FILTERS)}
        roles={roles}
        businessGroups={businessGroups}
        owners={owners}
        approvers={approvers}
      />
    </div>
  );
}

export default CompPlansCatalog;
