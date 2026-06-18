import { useState, useEffect } from "react";
import api from "../api";
import StatusPill from "../Components/StatusPill";
import PeriodFilter from "../Components/PeriodFilter";
import PageHeader from "../Components/PageHeader";
import "../Components/enterprise.css";

function Payouts() {
  const [runs, setRuns] = useState([]);
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.get("payout-runs/");
      setRuns(response.data);
    } catch (err) {
      setMessage(err.response?.data?.error || "Unable to load payout runs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name || !startDate || !endDate) {
      setMessage("Name and date range required.");
      return;
    }
    try {
      await api.post("payout-runs/", {
        name,
        start_date: startDate,
        end_date: endDate,
        notes: "",
      });
      setName("");
      setMessage("Payout run created (draft). Mark paid when transfer completes.");
      load();
    } catch (err) {
      setMessage(err.response?.data?.error || "Create failed.");
    }
  };

  const markPaid = async (runId) => {
    const ref = window.prompt("Payment reference (optional):", "");
    try {
      const response = await api.post(`payout-runs/${runId}/mark-paid/`, {
        payment_reference: ref || "",
      });
      setMessage(`Marked paid — ${response.data.commissions_paid} commission(s) updated.`);
      load();
    } catch (err) {
      setMessage(err.response?.data?.error || "Mark paid failed.");
    }
  };

  return (
    <div>
      <PageHeader badge="Payouts" title="Payout tracking" />

      <div className="panel">
        <form onSubmit={handleCreate}>
          <div className="enterprise-form-row">
            <label>
              Run name
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jan 2026 payroll" />
            </label>
          </div>
          <PeriodFilter
            startDate={startDate}
            endDate={endDate}
            onStartChange={setStartDate}
            onEndChange={setEndDate}
          />
          <button type="submit" className="btn-primary">Create draft run</button>
        </form>
        {message && <p className="banner">{message}</p>}
      </div>

      <div className="panel">
        {loading ? (
          <p>Loading…</p>
        ) : (
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Period</th>
                <th>Status</th>
                <th>Reference</th>
                <th>Paid commissions</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.name}</td>
                  <td>{run.start_date} → {run.end_date}</td>
                  <td><StatusPill status={run.status} /></td>
                  <td>{run.payment_reference || "—"}</td>
                  <td>{run.commission_count ?? 0}</td>
                  <td>
                    {run.status === "draft" && (
                      <button type="button" className="btn-secondary" onClick={() => markPaid(run.id)}>
                        Mark paid
                      </button>
                    )}
                    {run.paid_at && (
                      <small>{new Date(run.paid_at).toLocaleString()}</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default Payouts;
