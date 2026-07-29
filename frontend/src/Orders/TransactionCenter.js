import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import UploadFileOutlinedIcon from "@mui/icons-material/UploadFileOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import LoadingCenter from "../Components/LoadingCenter";
import { ImportDrawer, OverflowActionsMenu } from "../Components/Import";
import { ORDERS_IMPORT_CONFIG } from "../Components/Import/importConfigs";
import TransactionKpis from "./TransactionKpis";
import TransactionActionCenter from "./TransactionActionCenter";
import TransactionDataGrid from "./TransactionDataGrid";
import TransactionFilterDrawer from "./TransactionFilterDrawer";

const EMPTY_FILTERS = {
  q: "",
  order_status: "",
  commission_status: "",
  sales_rep: "",
  customer: "",
  product: "",
  region: "",
  business_group: "",
  source: "",
  date_from: "",
  date_to: "",
  amount_min: "",
  amount_max: "",
  missing_rep: "",
};

function TransactionCenter({ refreshKey = 0 }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { success, error, warning } = useToast();
  const [orders, setOrders] = useState([]);
  const [summary, setSummary] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [busy, setBusy] = useState(false);
  const [actionBanner, setActionBanner] = useState(null);
  const [importOpen, setImportOpen] = useState(false);

  const queryParams = useMemo(() => {
    const params = {};
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== "" && value != null) params[key] = value;
    });
    return params;
  }, [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ordersRes, summaryRes, profileRes] = await Promise.all([
        api.get("orders/", { params: queryParams }),
        api.get("orders/summary/"),
        api.get("user-profile/"),
      ]);
      let rows = Array.isArray(ordersRes.data)
        ? ordersRes.data
        : ordersRes.data.results || [];
      if (filters.commission_status) {
        rows = rows.filter(
          (o) => String(o.commission_status || "") === filters.commission_status
        );
      }
      setOrders(rows);
      setSummary(summaryRes.data);
      setIsAdmin(Boolean(profileRes.data.is_admin));
      setSelectedIds(new Set());
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load orders"));
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [queryParams, filters.commission_status, error]);

  useEffect(() => {
    const t = setTimeout(load, filters.q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, filters.q, refreshKey]);

  const resolveAction = (item) => {
    setActionBanner(item.title);
    setFilters((prev) => ({
      ...EMPTY_FILTERS,
      ...(item.filter || {}),
    }));
  };

  const bulk = async (action, extra = {}) => {
    if (!selectedIds.size) return;
    setBusy(true);
    try {
      const res = await api.post("orders/bulk/", {
        action,
        ids: Array.from(selectedIds),
        ...extra,
      });
      success(`${action}: ${res.data.updated} order(s) updated`);
      await load();
    } catch (err) {
      error(getApiErrorMessage(err, `Bulk ${action} failed`));
    } finally {
      setBusy(false);
    }
  };

  const approveOne = async (order) => {
    setBusy(true);
    try {
      const response = await api.patch(`orders/${order.id}/`, {
        order_status: "Success",
      });
      const updated = response.data;
      if (updated.has_commission) {
        success(`${order.order_id} approved — commission calculated`);
      } else {
        warning(
          updated.commission_skip_reason ||
            `${order.order_id} approved — no commission yet`
        );
      }
      await load();
    } catch (err) {
      error(getApiErrorMessage(err, "Approve failed"));
    } finally {
      setBusy(false);
    }
  };

  const exportSelected = () => {
    const selected = orders.filter((o) => selectedIds.has(o.id));
    const rows = selected.length ? selected : orders;
    const header = [
      "Order ID",
      "Customer",
      "Product",
      "Sales Rep",
      "Amount",
      "Status",
      "Commission Status",
      "Commission Amount",
      "Plan",
    ];
    const lines = rows.map((o) =>
      [
        o.order_id,
        o.customer || o.customer_name || "",
        o.product || o.product_name || "",
        o.sales_rep || o.employee_id || "",
        o.sales_amount,
        o.lifecycle_status || o.order_status,
        o.commission_status || "",
        o.commission_amount || "",
        o.commission_plan_name || "",
      ]
        .map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "orders.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const filterCount = Object.entries(filters).filter(
    ([k, v]) => k !== "q" && v !== "" && v != null
  ).length;

  useEffect(() => {
    if (searchParams.get("import") === "1") {
      setImportOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete("import");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const openImport = () => setImportOpen(true);

  const downloadTemplate = () => {
    const a = document.createElement("a");
    a.href = "/orders_template.csv";
    a.download = "orders_template.csv";
    a.click();
  };

  return (
    <div className="tx-console">
      <header className="tx-header">
        <div>
          <p className="tx-header__eyebrow">Orders</p>
          <h1 className="tx-header__title">Orders Center</h1>
          <p className="tx-header__sub">
            Manage sales orders, validate credits, and trigger commission calculations.
          </p>
        </div>
        <div className="tx-header__actions">
          <div className="tx-header__cta-group">
            <button type="button" className="btn-primary" onClick={() => navigate("/orders/new")}>
              + Create order
            </button>
            <OverflowActionsMenu
              ariaLabel="Order actions"
              items={[
                {
                  id: "import",
                  label: "Import Orders",
                  icon: <UploadFileOutlinedIcon fontSize="small" />,
                  onClick: openImport,
                },
                {
                  id: "template",
                  label: "Download Template",
                  icon: <DownloadOutlinedIcon fontSize="small" />,
                  onClick: downloadTemplate,
                },
                {
                  id: "export",
                  label: "Export Orders",
                  icon: <FileDownloadOutlinedIcon fontSize="small" />,
                  onClick: exportSelected,
                },
              ]}
            />
          </div>
        </div>
      </header>

      <TransactionKpis
        summary={summary}
        loading={loading && !summary}
        onFilterStatus={(order_status) =>
          setFilters((prev) => ({ ...prev, order_status, commission_status: "" }))
        }
      />

      <TransactionActionCenter
        summary={summary}
        loading={loading && !summary}
        onResolve={resolveAction}
      />

      <div className="tx-toolbar">
        <input
          type="search"
          className="tx-toolbar__search"
          placeholder="Search order ID, customer, rep, product…"
          value={filters.q}
          onChange={(e) => setFilters((prev) => ({ ...prev, q: e.target.value }))}
          aria-label="Search orders"
        />
        <button type="button" className="btn-secondary" onClick={() => setFilterOpen(true)}>
          Filters{filterCount ? ` (${filterCount})` : ""}
        </button>
        <button type="button" className="btn-secondary" onClick={load} disabled={loading}>
          Refresh
        </button>
        {(actionBanner || filterCount) ? (
          <button
            type="button"
            className="cp-btn-ghost"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setActionBanner(null);
            }}
          >
            Clear
          </button>
        ) : null}
      </div>

      {actionBanner ? (
        <div className="tx-banner" role="status">
          Showing: <strong>{actionBanner}</strong>
        </div>
      ) : null}

      {loading && orders.length === 0 ? (
        <LoadingCenter minHeight={220} />
      ) : (
        <TransactionDataGrid
          orders={orders}
          loading={loading}
          isAdmin={isAdmin}
          busy={busy}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onApprove={approveOne}
          onBulkApprove={() => bulk("approve")}
          onBulkReject={() => bulk("reject")}
          onBulkCalculate={() => bulk("calculate")}
          onBulkExport={exportSelected}
          onAssignRep={async () => {
            const employee_id = window.prompt("Assign sales rep (employee ID):");
            if (employee_id) await bulk("assign_rep", { employee_id });
          }}
        />
      )}

      <TransactionFilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(EMPTY_FILTERS)}
      />

      <ImportDrawer
        open={importOpen}
        onClose={() => setImportOpen(false)}
        config={ORDERS_IMPORT_CONFIG}
        onImported={(result) => {
          if ((result?.imported || 0) > 0) {
            success(`${result.imported} order(s) imported`);
          } else if ((result?.failed || 0) > 0) {
            warning("Import finished with errors — download the error report for details");
          }
          load();
        }}
      />
    </div>
  );
}

export default TransactionCenter;
