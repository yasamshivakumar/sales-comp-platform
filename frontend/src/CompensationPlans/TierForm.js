import { useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import { currencyForBusinessGroup } from "../utils/businessGroups";

function TierForm({ selectedPlan, onTierUpdated }) {
  const { error } = useToast();
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    tier_name: "",
    from_amount: "0",
    to_amount: "",
    commission_rate: "",
    bonus_amount: "0",
  });

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
        await api.patch(`compensation-plans/${selectedPlan.id}/`, {
          sc_flat_rate_tables: [
            ...existing.map(({ flat_rate, is_active }) => ({
              flat_rate,
              is_active: is_active !== false,
            })),
            { flat_rate: rate, is_active: true },
          ],
        });
      } else {
        const existing = selectedPlan.sc_rate_tables || [];
        const nextSequence =
          existing.reduce((max, row) => Math.max(max, row.sequence || 0), 0) + 1;
        const newRow = {
          tier_name: form.tier_name.trim() || `Tier ${nextSequence}`,
          from_amount: form.from_amount === "" ? 0 : form.from_amount,
          to_amount: form.to_amount === "" ? null : form.to_amount,
          commission_rate: rate,
          bonus_amount: form.bonus_amount === "" ? 0 : form.bonus_amount,
          sequence: nextSequence,
          is_active: true,
        };
        await api.patch(`compensation-plans/${selectedPlan.id}/`, {
          sc_rate_tables: [
            ...existing.map(
              ({
                tier_name,
                from_amount,
                to_amount,
                commission_rate,
                bonus_amount,
                sequence,
                is_active,
              }) => ({
                tier_name,
                from_amount,
                to_amount,
                commission_rate,
                bonus_amount,
                sequence,
                is_active: is_active !== false,
              })
            ),
            newRow,
          ],
        });
      }

      setForm({
        tier_name: "",
        from_amount: "0",
        to_amount: "",
        commission_rate: "",
        bonus_amount: "0",
      });
      onTierUpdated();
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

  const isFlat = selectedPlan.commission_table_type === "FLAT";
  const currency = selectedPlan?.currency || currencyForBusinessGroup(selectedPlan?.business_group || "", "");
  const amountLabel = currency || "order currency";

  return (
    <div className="panel">
      <h3 className="panel__title">Add commission rate</h3>

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
        <button
          type="button"
          className="btn-success"
          onClick={saveTier}
          disabled={loading}
        >
          {loading ? "Saving…" : "Save rate"}
        </button>
      </div>
    </div>
  );
}

export default TierForm;
