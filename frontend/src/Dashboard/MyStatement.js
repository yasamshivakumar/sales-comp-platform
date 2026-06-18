import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../api";
import PageHeader from "../Components/PageHeader";
import PeriodFilter from "../Components/PeriodFilter";
import StatusPill from "../Components/StatusPill";
import CommissionExplanationModal from "../Components/CommissionExplanationModal";
import DisputesPanel from "../Enterprise/DisputesPanel";
import { formatMoney, formatMoneyList } from "../utils/currency";
import "../Components/enterprise.css";
import "./statement.css";

const TABS = [
  { id: "orders", label: "Orders" },
  { id: "credits", label: "Credits" },
  { id: "rates", label: "Commission rate" },
  { id: "earned", label: "Commission earned" },
  { id: "adjustments", label: "Adjustments" },
  { id: "payout", label: "Payout status" },
];

function formatRate(value) {
  if (value == null || value === "") return "—";
  return `${parseFloat(value).toFixed(2)}%`;
}

function StatementTable({ columns, rows, emptyMessage, onRowClick }) {
  if (!rows?.length) {
    return <p className="stmt-empty">{emptyMessage}</p>;
  }
  return (
    <div className="stmt-table-wrap">
      <table className="enterprise-table stmt-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={col.align ? { textAlign: col.align } : undefined}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={row.id ?? `${row.order_id}-${index}`}
              className={onRowClick && row.id ? "stmt-row--clickable" : undefined}
              onClick={onRowClick && row.id ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} style={col.align ? { textAlign: col.align } : undefined}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MyStatement() {
  const [statement, setStatement] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [activeTab, setActiveTab] = useState("orders");
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [canManagePayroll, setCanManagePayroll] = useState(false);
  const [explainId, setExplainId] = useState(null);
  const [disputePrefill, setDisputePrefill] = useState(null);
  const disputesPanelRef = useRef(null);

  const openDisputeFor = (row) => {
    if (!row?.id || row.has_open_dispute) return;
    setDisputePrefill({
      id: row.id,
      order_id: row.order_id,
      order_date: row.order_date,
      employee_name: row.employee_name,
      employee_id: statement?.employee_id,
      commission_amount: row.commission_amount,
      status: row.status,
      has_open_dispute: row.has_open_dispute,
    });
    window.setTimeout(() => {
      disputesPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  const disputeActionColumn = {
    key: "dispute",
    label: "",
    render: (row) =>
      row.id && !row.has_open_dispute ? (
        <button
          type="button"
          className="btn-secondary stmt-dispute-btn"
          onClick={(e) => {
            e.stopPropagation();
            openDisputeFor(row);
          }}
        >
          Dispute
        </button>
      ) : row.has_open_dispute ? (
        <span className="stmt-dispute-open">Open</span>
      ) : null,
  };

  useEffect(() => {
    api
      .get("user-profile/")
      .then((res) => {
        const admin = Boolean(res.data.is_admin);
        const finance = Boolean(res.data.is_finance);
        const manager = Boolean(res.data.is_manager);
        setCanManagePayroll(admin || finance || manager);
      })
      .catch(() => setCanManagePayroll(false))
      .finally(() => setProfileLoaded(true));
  }, []);

  const loadStatement = useCallback(async () => {
    setLoading(true);
    setMessage("");
    try {
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      const qs = params.toString();
      const response = await api.get(qs ? `statements/me/?${qs}` : "statements/me/");
      setStatement(response.data);
    } catch (err) {
      setMessage(err.response?.data?.error || "Failed to load your statement.");
      setStatement(null);
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    loadStatement();
  }, [loadStatement]);

  const handleExport = async () => {
    try {
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      const response = await api.get(`statements/export/?${params.toString()}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `my-statement-${new Date().toISOString().split("T")[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setMessage("Export failed.");
    }
  };

  const summary = statement?.summary;
  const defaultCurrency = statement?.personal_currency || "INR";
  const money = (value, currency) => formatMoney(value, currency || defaultCurrency);
  const summaryAmount = (valueKey) => {
    const formatted = formatMoneyList(statement?.currency_summary, valueKey);
    if (formatted) return formatted;
    return money(summary?.[valueKey]);
  };

  const orderColumns = [
    { key: "order", label: "Order", render: (row) => row.order_id || "—" },
    { key: "date", label: "Date", render: (row) => row.order_date || "—" },
    { key: "product", label: "Product", render: (row) => row.product || "—" },
    {
      key: "sales",
      label: "Sales",
      align: "right",
      render: (row) => (row.sales_amount ? money(row.sales_amount, row.currency) : "—"),
    },
    {
      key: "rate",
      label: "Rate",
      align: "right",
      render: (row) => formatRate(row.commission_rate),
    },
    {
      key: "commission",
      label: "Commission",
      align: "right",
      render: (row) => money(row.commission_amount, row.currency),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => <StatusPill status={row.status} />,
    },
    disputeActionColumn,
  ];

  const creditColumns = [
    { key: "order", label: "Source order", render: (row) => row.order_id || "—" },
    { key: "date", label: "Date", render: (row) => row.order_date || "—" },
    { key: "reason", label: "Credit type", render: (row) => row.credit_reason || "Credit" },
    {
      key: "commission",
      label: "Amount",
      align: "right",
      render: (row) => money(row.commission_amount, row.currency),
    },
    { key: "plan", label: "Plan", render: (row) => row.plan_name || "—" },
    {
      key: "status",
      label: "Status",
      render: (row) => <StatusPill status={row.status} />,
    },
    disputeActionColumn,
  ];

  const rateColumns = [
    { key: "order", label: "Order", render: (row) => row.order_id || "—" },
    { key: "plan", label: "Plan", render: (row) => row.plan_name || "—" },
    {
      key: "sales",
      label: "Sales base",
      align: "right",
      render: (row) => (row.sales_amount ? money(row.sales_amount, row.currency) : "—"),
    },
    {
      key: "rate",
      label: "Effective rate",
      align: "right",
      render: (row) => formatRate(row.commission_rate),
    },
    {
      key: "commission",
      label: "Commission",
      align: "right",
      render: (row) => money(row.commission_amount, row.currency),
    },
    {
      key: "type",
      label: "Type",
      render: (row) => (row.line_type === "credit" ? "Credit" : "Order"),
    },
    disputeActionColumn,
  ];

  const earnedRows = (statement?.lines || []).filter(
    (row) => row.status !== "no_commission" && parseFloat(row.commission_amount) > 0
  );

  const earnedByPlan = earnedRows.reduce((acc, row) => {
    const key = row.plan_name || "Unassigned plan";
    if (!acc[key]) acc[key] = { plan: key, count: 0, total: 0 };
    acc[key].count += 1;
    acc[key].total += parseFloat(row.commission_amount) || 0;
    return acc;
  }, {});

  const adjustmentColumns = [
    { key: "order", label: "Order", render: (row) => row.order_id || "—" },
    { key: "message", label: "Adjustment", render: (row) => row.message },
    {
      key: "amount",
      label: "Commission",
      align: "right",
      render: (row) => money(row.commission_amount, row.currency),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => <StatusPill status={row.status} />,
    },
    {
      key: "resolved",
      label: "Resolved",
      render: (row) => (row.resolved_at ? row.resolved_at.split("T")[0] : "—"),
    },
  ];

  const allRateLines = statement?.lines?.filter((row) => row.commission_rate != null) || [];

  if (profileLoaded && canManagePayroll) {
    return <Navigate to="/commissions" replace />;
  }

  return (
    <div className="my-statement">
      <PageHeader badge="Your earnings" title="Incentives Details" />

      <div className="stmt-hero">
        <div className="stmt-hero__identity">
          <h2 className="stmt-hero__name">{statement?.employee_name || "—"}</h2>
          <p className="stmt-hero__meta">
            {[statement?.employee_id, statement?.position_name, statement?.territory_name]
              .filter(Boolean)
              .join(" · ") || statement?.employee_email}
          </p>
          {(statement?.start_date || statement?.end_date) && (
            <p className="stmt-hero__period">
              Period: {statement.start_date || "—"} to {statement.end_date || "—"}
            </p>
          )}
        </div>
        <div className="stmt-kpi-grid">
          <div className="stmt-kpi">
            <span className="stmt-kpi__label">Commission earned</span>
            <span className="stmt-kpi__value">
              {summaryAmount("total_commission_earned")}
            </span>
          </div>
          <div className="stmt-kpi">
            <span className="stmt-kpi__label">Pending payout</span>
            <span className="stmt-kpi__value stmt-kpi__value--pending">
              {summaryAmount("pending_payout")}
            </span>
          </div>
          <div className="stmt-kpi">
            <span className="stmt-kpi__label">Paid</span>
            <span className="stmt-kpi__value stmt-kpi__value--paid">
              {summaryAmount("paid_total")}
            </span>
          </div>
        </div>
      </div>

      <PeriodFilter
        startDate={startDate}
        endDate={endDate}
        onStartChange={setStartDate}
        onEndChange={setEndDate}
        onSubmit={loadStatement}
        loading={loading}
        submitLabel="Update period"
      >
        <button type="button" className="btn-secondary" onClick={handleExport} disabled={!statement}>
          Download CSV
        </button>
      </PeriodFilter>

      {message && <p className="banner">{message}</p>}

      <div className="stmt-tabs view-tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && !statement ? (
        <div className="stmt-loading">Loading your statement…</div>
      ) : (
        <div className="stmt-panel panel">
          <p className="stmt-hint">
            Click any commission row to see how it was calculated. Use <strong>Dispute</strong> to
            report an issue — admins will review it on the Commissions page.
          </p>
          {activeTab === "orders" && (
            <StatementTable
              columns={orderColumns}
              rows={statement?.orders}
              emptyMessage="No orders in this period."
              onRowClick={(row) => setExplainId(row.id)}
            />
          )}

          {activeTab === "credits" && (
            <StatementTable
              columns={creditColumns}
              rows={statement?.credits}
              emptyMessage="No hierarchy credits or overrides in this period."
              onRowClick={(row) => setExplainId(row.id)}
            />
          )}

          {activeTab === "rates" && (
            <StatementTable
              columns={rateColumns}
              rows={allRateLines}
              emptyMessage="No commission rates calculated for this period."
              onRowClick={(row) => setExplainId(row.id)}
            />
          )}

          {activeTab === "earned" && (
            <>
              <StatementTable
                columns={[
                  { key: "plan", label: "Comp plan", render: (row) => row.plan },
                  {
                    key: "count",
                    label: "Deals",
                    align: "right",
                    render: (row) => row.count,
                  },
                  {
                    key: "total",
                    label: "Earned",
                    align: "right",
                    render: (row) => money(row.total),
                  },
                ]}
                rows={Object.values(earnedByPlan)}
                emptyMessage="No commission earned in this period."
              />
              {earnedRows.length > 0 && (
                <div className="stmt-subsection">
                  <h3 className="stmt-subsection__title">Line detail</h3>
                  <StatementTable
                    columns={orderColumns}
                    rows={earnedRows}
                    emptyMessage=""
                  />
                </div>
              )}
            </>
          )}

          {activeTab === "adjustments" && (
            <StatementTable
              columns={adjustmentColumns}
              rows={statement?.adjustments}
              emptyMessage="No adjustments or disputes on your commissions."
            />
          )}

          {activeTab === "payout" && (
            <>
              <div className="stmt-payout-grid">
                {(statement?.payout_status || []).map((bucket) => (
                  <div key={bucket.status} className="stmt-payout-card">
                    <StatusPill status={bucket.status} label={bucket.label} />
                    <p className="stmt-payout-card__amount">{money(bucket.amount)}</p>
                    <p className="stmt-payout-card__count">{bucket.count} line(s)</p>
                  </div>
                ))}
              </div>
              <div className="stmt-subsection">
                <h3 className="stmt-subsection__title">Payout timeline</h3>
                <StatementTable
                  columns={[
                    { key: "order", label: "Order", render: (row) => row.order_id || "—" },
                    {
                      key: "commission",
                      label: "Commission",
                      align: "right",
                      render: (row) => money(row.commission_amount, row.currency),
                    },
                    {
                      key: "status",
                      label: "Status",
                      render: (row) => <StatusPill status={row.status} />,
                    },
                    {
                      key: "calculated",
                      label: "Calculated",
                      render: (row) =>
                        row.calculated_at ? row.calculated_at.split("T")[0] : "—",
                    },
                    {
                      key: "approved",
                      label: "Approved",
                      render: (row) =>
                        row.approved_at ? row.approved_at.split("T")[0] : "—",
                    },
                    {
                      key: "paid",
                      label: "Paid",
                      render: (row) => (row.paid_at ? row.paid_at.split("T")[0] : "—"),
                    },
                  ]}
                  rows={statement?.lines?.filter((row) => row.id)}
                  emptyMessage="No payout lines in this period."
                  onRowClick={(row) => setExplainId(row.id)}
                />
              </div>
            </>
          )}
        </div>
      )}

      <CommissionExplanationModal
        open={Boolean(explainId)}
        commissionId={explainId}
        onClose={() => setExplainId(null)}
        periodStart={startDate}
        periodEnd={endDate}
      />

      <DisputesPanel
        panelRef={disputesPanelRef}
        canResolve={false}
        employeeMode
        prefillCommission={disputePrefill}
        onPrefillConsumed={() => setDisputePrefill(null)}
        onSubmitted={loadStatement}
      />
    </div>
  );
}

export default MyStatement;
