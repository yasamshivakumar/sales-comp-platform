import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import { currencyForBusinessGroup } from "../utils/businessGroups";

const EMPTY = {
  tier_name: "",
  product_name: "",
  service_name: "",
  distribution: "",
  from_amount: "0",
  to_amount: "",
  commission_rate: "",
  bonus_amount: "0",
};

function cleanLookupRow(row) {
  return {
    tier_name: row.tier_name || "",
    product_name: row.product_name || "",
    service_name: row.service_name || "",
    distribution: row.distribution || "",
    from_amount: row.from_amount === "" || row.from_amount == null ? 0 : row.from_amount,
    to_amount: row.to_amount === "" || row.to_amount == null ? null : row.to_amount,
    commission_rate: row.commission_rate,
    bonus_amount: row.bonus_amount === "" || row.bonus_amount == null ? 0 : row.bonus_amount,
    sequence: row.sequence || 1,
    is_active: row.is_active !== false,
  };
}

function formFromEditingTier(editingTier) {
  if (!editingTier?.row) return EMPTY;
  return {
    tier_name: editingTier.row.tier_name || "",
    product_name: editingTier.row.product_name || "",
    service_name: editingTier.row.service_name || "",
    distribution: editingTier.row.distribution || "",
    from_amount: editingTier.row.from_amount ?? "0",
    to_amount: editingTier.row.to_amount ?? "",
    commission_rate: editingTier.row.commission_rate ?? "",
    bonus_amount: editingTier.row.bonus_amount ?? "0",
  };
}

function LookupTierForm({ selectedPlan, editingTier = null, onTierUpdated, onCancelEdit }) {
  const { error } = useToast();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(() => formFromEditingTier(editingTier));
  const currency = selectedPlan?.currency || currencyForBusinessGroup(selectedPlan?.business_group || "", "");
  const amountLabel = currency || "order currency";
  const editing = Boolean(editingTier);

  useEffect(() => {
    setForm(formFromEditingTier(editingTier));
  }, [editingTier]);

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
      const existing = selectedPlan.sc_lookup_tables || [];
      const nextSequence =
        existing.reduce((max, row) => Math.max(max, row.sequence || 0), 0) + 1;
      const newRow = cleanLookupRow({
        ...(editingTier?.row || {}),
        tier_name: form.tier_name.trim() || `Lookup ${nextSequence}`,
        product_name: form.product_name.trim(),
        service_name: form.service_name.trim(),
        distribution: form.distribution.trim(),
        from_amount: form.from_amount === "" ? 0 : form.from_amount,
        to_amount: form.to_amount === "" ? null : form.to_amount,
        commission_rate: rate,
        bonus_amount: form.bonus_amount === "" ? 0 : form.bonus_amount,
        sequence: editingTier?.row?.sequence || nextSequence,
        is_active: true,
      });
      const rows = editing
        ? existing.map((row, index) =>
            index === editingTier.index ? newRow : cleanLookupRow(row)
          )
        : [...existing.map(cleanLookupRow), newRow];
      await api.patch(`compensation-plans/${selectedPlan.id}/`, {
        sc_lookup_tables: rows,
      });
      setForm(EMPTY);
      onTierUpdated();
      onCancelEdit?.();
    } catch (err) {
      const data = err.response?.data;
      error(
        (typeof data === "object" && data && Object.values(data).flat().join(", ")) ||
          "Error saving lookup tier"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3 className="panel__title">{editing ? "Edit lookup tier" : "Add lookup tier"}</h3>
      <p className="comp-plans-toolbar__hint" style={{ marginTop: 0 }}>
        Match orders by product, service, and/or distribution. Leave a dimension blank to
        match any value. More specific rows win over wildcards.
      </p>
      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="lookup_tier_name">Tier name</label>
          <input id="lookup_tier_name" name="tier_name" value={form.tier_name} onChange={handleChange} placeholder="Optional label" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_product">Product</label>
          <input id="lookup_product" name="product_name" value={form.product_name} onChange={handleChange} placeholder="Any if blank" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_service">Service</label>
          <input id="lookup_service" name="service_name" value={form.service_name} onChange={handleChange} placeholder="Any if blank" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_distribution">Distribution</label>
          <input id="lookup_distribution" name="distribution" value={form.distribution} onChange={handleChange} placeholder="Any if blank" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_from">From amount ({amountLabel})</label>
          <input id="lookup_from" type="number" name="from_amount" value={form.from_amount} onChange={handleChange} min="0" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_to">To amount ({amountLabel})</label>
          <input id="lookup_to" type="number" name="to_amount" value={form.to_amount} onChange={handleChange} placeholder="Blank = no limit" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_rate">Commission %</label>
          <input id="lookup_rate" type="number" name="commission_rate" value={form.commission_rate} onChange={handleChange} min="0" step="0.01" />
        </div>
        <div className="form-field">
          <label htmlFor="lookup_bonus">Bonus amount ({amountLabel})</label>
          <input id="lookup_bonus" type="number" name="bonus_amount" value={form.bonus_amount} onChange={handleChange} min="0" />
        </div>
      </div>
      <div className="form-actions">
        {editing && (
          <button type="button" className="btn-secondary" onClick={onCancelEdit} disabled={loading}>
            Cancel edit
          </button>
        )}
        <button type="button" className="btn-success" onClick={saveTier} disabled={loading}>
          {loading ? "Saving…" : editing ? "Update lookup tier" : "Save lookup tier"}
        </button>
      </div>
    </div>
  );
}

export default LookupTierForm;
