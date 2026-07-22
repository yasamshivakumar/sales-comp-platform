import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import { currencyForBusinessGroup } from "../utils/businessGroups";

const EMPTY_RATE_FORM = {
  tier_name: "",
  from_amount: "0",
  to_amount: "",
  commission_rate: "",
  bonus_amount: "0",
};

function cleanRateRow(row) {
  return {
    tier_name: row.tier_name || "",
    from_amount: row.from_amount === "" || row.from_amount == null ? 0 : row.from_amount,
    to_amount: row.to_amount === "" || row.to_amount == null ? null : row.to_amount,
    commission_rate: row.commission_rate,
    bonus_amount: row.bonus_amount === "" || row.bonus_amount == null ? 0 : row.bonus_amount,
    sequence: row.sequence || 1,
    is_active: row.is_active !== false,
  };
}

function cleanFlatRow(row) {
  return {
    minimum_sales_threshold:
      row.minimum_sales_threshold === "" || row.minimum_sales_threshold == null
        ? 0
        : row.minimum_sales_threshold,
    flat_rate: row.flat_rate,
    bonus_amount: row.bonus_amount === "" || row.bonus_amount == null ? 0 : row.bonus_amount,
    is_active: row.is_active !== false,
  };
}

function formFromEditingTier(editingTier, isFlat) {
  if (!editingTier?.row) return EMPTY_RATE_FORM;
  if (isFlat) {
    return {
      ...EMPTY_RATE_FORM,
      commission_rate: editingTier.row.flat_rate ?? "",
      bonus_amount: editingTier.row.bonus_amount ?? "0",
    };
  }
  return {
    tier_name: editingTier.row.tier_name || "",
    from_amount: editingTier.row.from_amount ?? "0",
    to_amount: editingTier.row.to_amount ?? "",
    commission_rate: editingTier.row.commission_rate ?? "",
    bonus_amount: editingTier.row.bonus_amount ?? "0",
  };
}

function TierForm({ selectedPlan, editingTier = null, onTierUpdated, onCancelEdit }) {
  const { error } = useToast();
  const [loading, setLoading] = useState(false);
  const isFlat = selectedPlan.commission_table_type === "FLAT";
  const isHighest = selectedPlan.commission_table_type === "HIGHEST";
  const isMarginal = selectedPlan.commission_table_type === "MARGINAL";

  const [form, setForm] = useState(() => formFromEditingTier(editingTier, isFlat));
  const editing = Boolean(editingTier);

  useEffect(() => {
    setForm(formFromEditingTier(editingTier, isFlat));
  }, [editingTier, isFlat]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const saveTier = async () => {
    const rate = parseFloat(form.commission_rate);
    if (Number.isNaN(rate) || rate <= 0) {
      error("Commission rate % is required");
      return;
    }

    setLoading(true);
    try {
      if (selectedPlan.commission_table_type === "FLAT") {
        const existing = selectedPlan.sc_flat_rate_tables || [];
        const newRow = cleanFlatRow({
          ...(editingTier?.row || {}),
          flat_rate: rate,
          bonus_amount: form.bonus_amount,
        });
        const rows = editing
          ? existing.map((row, index) =>
              index === editingTier.index ? newRow : cleanFlatRow(row)
            )
          : [...existing.map(cleanFlatRow), newRow];
        await api.patch(`compensation-plans/${selectedPlan.id}/`, {
          sc_flat_rate_tables: rows,
        });
      } else {
        const existing = selectedPlan.sc_rate_tables || [];
        const nextSequence =
          existing.reduce((max, row) => Math.max(max, row.sequence || 0), 0) + 1;
        const newRow = cleanRateRow({
          ...(editingTier?.row || {}),
          tier_name: form.tier_name.trim() || `Tier ${nextSequence}`,
          from_amount: form.from_amount === "" ? 0 : form.from_amount,
          to_amount: form.to_amount === "" ? null : form.to_amount,
          commission_rate: rate,
          bonus_amount: form.bonus_amount === "" ? 0 : form.bonus_amount,
          sequence: editingTier?.row?.sequence || nextSequence,
          is_active: true,
        });
        const rows = editing
          ? existing.map((row, index) =>
              index === editingTier.index ? newRow : cleanRateRow(row)
            )
          : [...existing.map(cleanRateRow), newRow];
        await api.patch(`compensation-plans/${selectedPlan.id}/`, {
          sc_rate_tables: rows,
        });
      }

      setForm(EMPTY_RATE_FORM);
      onTierUpdated();
      onCancelEdit?.();
    } catch (err) {
      const data = err.response?.data;
      error(
        (typeof data === "object" && data && Object.values(data).flat().join(", ")) ||
          "Error saving commission rate"
      );
    } finally {
      setLoading(false);
    }
  };

  const currency = selectedPlan?.currency || currencyForBusinessGroup(selectedPlan?.business_group || "", "");
  const amountLabel = currency || "order currency";

  return (
    <div className="panel">
      <h3 className="panel__title">
        {editing
          ? isHighest
            ? "Edit highest-rate band"
            : isMarginal
              ? "Edit marginal band"
              : "Edit commission rate"
          : isHighest
            ? "Add highest-rate band"
            : isMarginal
              ? "Add marginal band"
              : "Add commission rate"}
      </h3>
      {isHighest && (
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
          These bands apply to the employee’s monthly sales total. The matching tier’s rate is
          applied to the entire monthly sum.
        </p>
      )}
      {isMarginal && (
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 0 }}>
          These bands fill up as orders come in — each order tops up the current band’s leftover at
          its rate, then the rest of that order is paid at the next band’s rate. The top band is
          open-ended.
        </p>
      )}

      {isFlat ? (
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="commission_rate">Flat commission %</label>
            <input
              id="commission_rate"
              type="number"
              name="commission_rate"
              value={form.commission_rate}
              onChange={handleChange}
              placeholder="e.g. 3"
              min="0"
              step="0.01"
            />
          </div>
        </div>
      ) : (
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="tier_name">Tier name</label>
            <input
              id="tier_name"
              name="tier_name"
              value={form.tier_name}
              onChange={handleChange}
              placeholder="Optional label"
            />
          </div>
          <div className="form-field">
            <label htmlFor="from_amount">From amount ({amountLabel})</label>
            <input
              id="from_amount"
              type="number"
              name="from_amount"
              value={form.from_amount}
              onChange={handleChange}
              min="0"
            />
          </div>
          <div className="form-field">
            <label htmlFor="to_amount">To amount ({amountLabel})</label>
            <input
              id="to_amount"
              type="number"
              name="to_amount"
              value={form.to_amount}
              onChange={handleChange}
              placeholder="Blank = no upper limit"
            />
          </div>
          <div className="form-field">
            <label htmlFor="commission_rate">Commission %</label>
            <input
              id="commission_rate"
              type="number"
              name="commission_rate"
              value={form.commission_rate}
              onChange={handleChange}
              placeholder="e.g. 5"
              min="0"
              step="0.01"
            />
          </div>
          <div className="form-field">
            <label htmlFor="bonus_amount">Bonus amount ({amountLabel})</label>
            <input
              id="bonus_amount"
              type="number"
              name="bonus_amount"
              value={form.bonus_amount}
              onChange={handleChange}
              min="0"
            />
          </div>
        </div>
      )}

      <div className="form-actions">
        {editing && (
          <button type="button" className="btn-secondary" onClick={onCancelEdit} disabled={loading}>
            Cancel edit
          </button>
        )}
        <button type="button" className="btn-success" onClick={saveTier} disabled={loading}>
          {loading ? "Saving…" : editing ? "Update rate" : "Save rate"}
        </button>
      </div>
    </div>
  );
}

export default TierForm;
