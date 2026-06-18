import { useState, useEffect } from "react";
import api from "../api";
import PageHeader from "../Components/PageHeader";
import "../Components/enterprise.css";

function Territories() {
  const [territories, setTerritories] = useState([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.get("territories/");
      setTerritories(response.data);
    } catch {
      setTerritories([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim() || !code.trim()) return;
    setMessage("");
    try {
      await api.post("territories/", { name: name.trim(), code: code.trim(), is_active: true });
      setName("");
      setCode("");
      setMessage("Territory created.");
      load();
    } catch (err) {
      setMessage(err.response?.data?.detail || "Failed to create territory.");
    }
  };

  const toggleActive = async (territory) => {
    try {
      await api.patch(`territories/${territory.id}/`, {
        is_active: !territory.is_active,
      });
      load();
    } catch {
      setMessage("Update failed.");
    }
  };

  return (
    <div>
      <PageHeader badge="Territories" title="Territory management" />

      <div className="panel">
        <form className="enterprise-form-row" onSubmit={handleCreate}>
          <label>
            Name
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="North India" />
          </label>
          <label>
            Code
            <input className="input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="N-IN" />
          </label>
          <button type="submit" className="btn-primary">Add territory</button>
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
                <th>Code</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {territories.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td><code>{t.code}</code></td>
                  <td>{t.is_active ? "Active" : "Inactive"}</td>
                  <td>
                    <button type="button" className="btn-secondary" onClick={() => toggleActive(t)}>
                      {t.is_active ? "Deactivate" : "Activate"}
                    </button>
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

export default Territories;
