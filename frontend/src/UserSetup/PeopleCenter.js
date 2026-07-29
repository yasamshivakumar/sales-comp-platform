import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import MarkEmailUnreadOutlinedIcon from "@mui/icons-material/MarkEmailUnreadOutlined";
import SupervisorAccountOutlinedIcon from "@mui/icons-material/SupervisorAccountOutlined";
import TrendingUpOutlinedIcon from "@mui/icons-material/TrendingUpOutlined";
import PersonOffOutlinedIcon from "@mui/icons-material/PersonOffOutlined";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import { PageShell } from "../Components/enterprise";
import { ImportDrawer, OverflowActionsMenu } from "../Components/Import";
import { PEOPLE_IMPORT_CONFIG } from "../Components/Import/importConfigs";
import PeopleDataGrid, { PeopleColumnPicker, usePeopleColumns } from "./PeopleDataGrid";
import EmployeeDrawer from "./enterprise/EmployeeDrawer";
import BulkActionBar from "./enterprise/BulkActionBar";
import EnterpriseToolbar from "./enterprise/EnterpriseToolbar";

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
  {
    key: "total_employees",
    label: "Total Participants",
    subtitle: "All people in this company",
    view: "all",
    Icon: GroupsOutlinedIcon,
  },
  {
    key: "active_users",
    label: "Active Participants",
    subtitle: "Active & plan assigned",
    tone: "success",
    Icon: CheckCircleIcon,
  },
  {
    key: "pending_invitations",
    label: "Pending Invitations",
    subtitle: "Awaiting activation",
    tone: "warning",
    view: "pending",
    Icon: MarkEmailUnreadOutlinedIcon,
  },
  {
    key: "managers",
    label: "Managers",
    subtitle: "People leaders",
    view: "managers",
    Icon: SupervisorAccountOutlinedIcon,
  },
  {
    key: "sales_participants",
    label: "Sales Participants",
    subtitle: "Quota-carrying roles",
    tone: "teal",
    view: "sales",
    Icon: TrendingUpOutlinedIcon,
  },
  {
    key: "inactive_users",
    label: "Inactive",
    subtitle: "Suspended or inactive",
    tone: "danger",
    view: "inactive",
    Icon: PersonOffOutlinedIcon,
  },
];

function PeopleCenter() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { success, error } = useToast();
  const { visible, setVisible, columns } = usePeopleColumns();
  const [people, setPeople] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [viewId, setViewId] = useState("all");
  const [ordering, setOrdering] = useState("name");
  const [page, setPage] = useState(1);
  const [importOpen, setImportOpen] = useState(false);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [expandedId, setExpandedId] = useState(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [drawerPersonId, setDrawerPersonId] = useState(null);

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

  useEffect(() => {
    if (searchParams.get("import") === "1") {
      setImportOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete("import");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const downloadTemplate = () => {
    const a = document.createElement("a");
    a.href = "/user_setup_template.csv";
    a.download = "user_setup_template.csv";
    a.click();
  };

  return (
    <PageShell
      breadcrumbs={[
        { label: "Incentra", to: "/dashboard" },
        { label: "People & Access" },
      ]}
      title="Participant Management"
      subtitle="Enterprise directory for employees, plans, quota, hierarchy, and access."
      primaryAction={
        <button type="button" className="btn-primary" onClick={() => navigate("/user-setup/new")}>
          + Create person
        </button>
      }
    >
    <div className="pe-console pe-console--enterprise">
      <section className="pe-kpis pe-kpis--executive" aria-label="Summary">
        <div className="pe-kpis__grid pe-kpis__grid--exec">
          {KPI_DEFS.map((kpi) => {
            const raw = summary?.[kpi.key];
            const display = loading && !summary ? "—" : Number(raw || 0).toLocaleString();
            const Icon = kpi.Icon;
            return (
              <button
                type="button"
                key={kpi.key}
                className={`pe-kpi pe-kpi--card${kpi.tone ? ` pe-kpi--${kpi.tone}` : ""}${
                  kpi.view && viewId === kpi.view ? " is-active" : ""
                }`}
                onClick={() => kpi.view && setViewId(kpi.view)}
              >
                <span className="pe-kpi__icon" aria-hidden>
                  {Icon ? <Icon fontSize="small" /> : null}
                </span>
                <span className="pe-kpi__label">{kpi.label}</span>
                <span className="pe-kpi__value">{display}</span>
                <span className="pe-kpi__sub">{kpi.subtitle}</span>
              </button>
            );
          })}
        </div>
      </section>

      <EnterpriseToolbar
        search={filters.q}
        onSearchChange={(q) => setFilters((p) => ({ ...p, q }))}
        filterCount={filterCount}
        onOpenFilters={() => setFilterOpen(true)}
        viewId={viewId}
        views={SAVED_VIEWS}
        onViewChange={setViewId}
        ordering={ordering}
        onOrderingChange={setOrdering}
        columnPicker={<PeopleColumnPicker visible={visible} onChange={setVisible} />}
        onRefresh={load}
        refreshing={loading}
        bulkDisabled={!selectedIds.size || busy}
        bulkLabel={
          selectedIds.size ? `Bulk actions (${selectedIds.size})` : "Bulk actions"
        }
        onBulkClick={() => {
          if (!selectedIds.size) return;
          document
            .querySelector(".pe-bulk--float")
            ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }}
        createSlot={null}
        overflowSlot={
          <OverflowActionsMenu
            ariaLabel="More people actions"
            items={[
              {
                id: "import",
                label: "Import Employees",
                icon: <UploadFileOutlinedIcon fontSize="small" />,
                onClick: () => setImportOpen(true),
              },
              {
                id: "export",
                label: "Export Employees",
                icon: <FileDownloadOutlinedIcon fontSize="small" />,
                onClick: () => bulk("export"),
              },
              {
                id: "template",
                label: "Download Template",
                icon: <DownloadOutlinedIcon fontSize="small" />,
                onClick: downloadTemplate,
              },
              {
                id: "settings",
                label: "Settings",
                icon: <SettingsOutlinedIcon fontSize="small" />,
                onClick: () => setFilterOpen(true),
              },
            ]}
          />
        }
      />

      <BulkActionBar
        count={selectedIds.size}
        busy={busy}
        onAssignPlan={() => {
          const planName = window.prompt("Assign plan (exact plan name):");
          if (planName) bulk("assign_plan", { plan_name: planName });
        }}
        onUpdateQuota={() => {
          const quota = window.prompt("Update quota (numeric target):");
          if (quota != null && quota !== "") bulk("update_quota", { quota });
        }}
        onDeactivate={() => bulk("deactivate")}
        onExport={() => bulk("export")}
        onClear={() => setSelectedIds(new Set())}
      />

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
          onPreview={(person) => setDrawerPersonId(person.id)}
          onDeactivate={async (person) => {
            setBusy(true);
            try {
              const res = await api.post("user-setup/bulk/", {
                action: "deactivate",
                ids: [person.id],
              });
              success(`Updated ${res.data.updated} person(s)`);
              await load();
            } catch (err) {
              error(getApiErrorMessage(err, "Deactivate failed"));
            } finally {
              setBusy(false);
            }
          }}
        />

      <EmployeeDrawer
        open={Boolean(drawerPersonId)}
        personId={drawerPersonId}
        onClose={() => setDrawerPersonId(null)}
      />

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

      <ImportDrawer
        open={importOpen}
        onClose={() => setImportOpen(false)}
        config={PEOPLE_IMPORT_CONFIG}
        onImported={(result) => {
          if ((result?.imported || 0) > 0) {
            success(`${result.imported} employee(s) imported`);
          }
          load();
        }}
      />
    </div>
    </PageShell>
  );
}

export default PeopleCenter;
