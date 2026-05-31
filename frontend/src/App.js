import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "./api";
import { useToast } from "./Components/Toast";
import PageHeader from "./Components/PageHeader";

function App() {
  const [employees, setEmployees] = useState([]);
  const [commissionCount, setCommissionCount] = useState(0);
  const [totalPaid, setTotalPaid] = useState(0);
  const { error } = useToast();

  useEffect(() => {
    fetchEmployees();
    fetchCommissionSummary();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchEmployees = async () => {
    try {
      const response = await api.get("employees/");
      setEmployees(response.data);
    } catch {
      error("Failed to load employees");
    }
  };

  const fetchCommissionSummary = async () => {
    try {
      const response = await api.get("commissions/");
      const rows = response.data || [];
      setCommissionCount(rows.length);
      setTotalPaid(
        rows.reduce(
          (sum, c) => sum + parseFloat(c.commission_amount || 0),
          0
        )
      );
    } catch {
      error("Failed to load commission summary");
    }
  };

  return (
    <div>
      <PageHeader badge="Dashboard" title="Overview" />

      <div className="stats-grid" style={{ marginBottom: "24px" }}>
        <div className="stat-card">
          <div className="stat-card__icon">👥</div>
          <div>
            <p className="stat-card__label">Total Employees</p>
            <p className="stat-card__value">{employees.length}</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__icon">💰</div>
          <div>
            <p className="stat-card__label">Commission Records</p>
            <p className="stat-card__value">{commissionCount}</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__icon">💵</div>
          <div>
            <p className="stat-card__label">Total Amount</p>
            <p className="stat-card__value">
              ₹{totalPaid.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: "24px" }}>
        <p style={{ margin: "0 0 12px", color: "var(--text-secondary)" }}>
          Approve commissions, export payroll, and run reports on the Commissions page.
        </p>
        <Link to="/commissions" className="btn-primary" style={{ display: "inline-block" }}>
          Open Commissions →
        </Link>
      </div>
    </div>
  );
}

export default App;
