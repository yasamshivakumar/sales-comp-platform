import { useCallback, useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import api, { getApiErrorMessage } from "../../api";
import { useToast } from "../../Components/Toast";
import LoadingCenter from "../../Components/LoadingCenter";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function emptyYearGrid(year) {
  return MONTHS.map((_, idx) => ({
    year,
    month: idx + 1,
    quota_amount: "",
    currency: "INR",
  }));
}

function QuotasTab() {
  const { plan, reloadPlan } = useOutletContext();
  const { success, error } = useToast();
  const [versions, setVersions] = useState([]);
  const [versionId, setVersionId] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [rows, setRows] = useState(() => emptyYearGrid(new Date().getFullYear()));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const selected = useMemo(
    () => versions.find((v) => String(v.id) === String(versionId)),
    [versions, versionId]
  );
  const editable = selected?.is_editable;

  const loadVersions = useCallback(async () => {
    if (!plan?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`compensation-plans/${plan.id}/versions/`);
      const list = res.data || [];
      setVersions(list);
      const preferred =
        list.find((v) => v.id === plan.current_version?.id) ||
        list.find((v) => v.status === "Draft") ||
        list[0];
      if (preferred) setVersionId(String(preferred.id));
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load versions"));
    } finally {
      setLoading(false);
    }
  }, [plan?.id, plan?.current_version?.id, error]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  useEffect(() => {
    if (!selected) return;
    const grid = emptyYearGrid(year);
    (selected.quotas || []).forEach((q) => {
      if (Number(q.year) !== Number(year)) return;
      const idx = Number(q.month) - 1;
      if (idx >= 0 && idx < 12) {
        grid[idx] = {
          year: Number(q.year),
          month: Number(q.month),
          quota_amount: String(q.quota_amount ?? ""),
          currency: q.currency || "INR",
        };
      }
    });
    setRows(grid);
  }, [selected, year]);

  const updateRow = (month, field, value) => {
    setRows((prev) =>
      prev.map((row) => (row.month === month ? { ...row, [field]: value } : row))
    );
  };

  const save = async () => {
    if (!selected || !editable) return;
    setSaving(true);
    try {
      const otherYears = (selected.quotas || []).filter(
        (q) => Number(q.year) !== Number(year)
      );
      const payload = [
        ...otherYears.map((q) => ({
          year: q.year,
          month: q.month,
          quota_amount: q.quota_amount,
          currency: q.currency || "",
        })),
        ...rows
          .filter((r) => String(r.quota_amount).trim() !== "")
          .map((r) => ({
            year: Number(year),
            month: r.month,
            quota_amount: r.quota_amount,
            currency: r.currency || "",
          })),
      ];
      await api.patch(`compensation-plans/${plan.id}/versions/${selected.id}/`, {
        quotas: payload,
      });
      success(`Quotas saved for v${selected.version_number} (${year}).`);
      await loadVersions();
      await reloadPlan();
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to save quotas"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingCenter minHeight={200} />;

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <h2 className="panel__title">Quotas</h2>
        <p className="cp-tab-lead">
          Monthly quota amounts on a plan version. Draft versions are editable; published
          versions are read-only.
        </p>

        <div className="cp-quota-controls">
          <label>
            Version
            <select value={versionId} onChange={(e) => setVersionId(e.target.value)}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_number} · {v.status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Year
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value) || year)}
              min={2000}
              max={2100}
            />
          </label>
          {editable && (
            <button type="button" className="btn-primary" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save quotas"}
            </button>
          )}
        </div>

        <div className="cp-quota-grid">
          {rows.map((row) => (
            <div key={row.month} className="cp-quota-cell">
              <span className="cp-quota-cell__month">{MONTHS[row.month - 1]}</span>
              <input
                type="number"
                step="0.01"
                placeholder="Amount"
                value={row.quota_amount}
                disabled={!editable}
                onChange={(e) => updateRow(row.month, "quota_amount", e.target.value)}
              />
              <input
                type="text"
                placeholder="CUR"
                value={row.currency}
                disabled={!editable}
                onChange={(e) => updateRow(row.month, "currency", e.target.value)}
                maxLength={8}
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default QuotasTab;
