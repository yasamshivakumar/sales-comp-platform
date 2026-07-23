import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { clearAuthStorage, getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";

const STEPS = ["Upload", "Validate", "Preview", "Import"];

function PeopleImportPage() {
  const [file, setFile] = useState(null);
  const [step, setStep] = useState(0);
  const [validation, setValidation] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const { success, error, warning } = useToast();

  const loadHistory = useCallback(async () => {
    try {
      const res = await api.get("user-setup-upload/history/");
      setHistory(res.data?.results || []);
    } catch {
      setHistory([]);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const validate = async () => {
    if (!file) {
      warning("Please select a CSV file");
      return;
    }
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("user-setup-upload/validate/", formData);
      setValidation(res.data);
      setStep(res.data.error_count ? 1 : 2);
      if (res.data.error_count) {
        warning(`${res.data.error_count} validation issue(s) found`);
      } else {
        success(`${res.data.valid_rows} row(s) ready to import`);
      }
    } catch (err) {
      error(getApiErrorMessage(err, "Validation failed"));
    } finally {
      setBusy(false);
    }
  };

  const importFile = async () => {
    if (!file) return;
    if (validation && validation.error_count > 0) {
      warning("Fix validation errors before importing");
      return;
    }
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("user-setup-upload/", formData);
      if (res.status === 202 || res.data?.job_id) {
        success(`Import queued / completed — job #${res.data?.job_id || "n/a"}`);
        setStep(3);
        await loadHistory();
        return;
      }
      const { success: ok = 0, failed = 0, errors = [] } = res.data || {};
      if (failed > 0) {
        warning(
          `Import finished — ${ok} succeeded, ${failed} failed. ${errors
            .slice(0, 2)
            .map((e) => `Row ${e.row}: ${e.error}`)
            .join(" ")}`
        );
      } else {
        success(`Import done — ${ok} employee(s)`);
      }
      setStep(3);
      await loadHistory();
    } catch (err) {
      if (err.response?.status === 401) {
        clearAuthStorage();
        window.location.href = "/login";
        return;
      }
      error(getApiErrorMessage(err, "Import failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pe-subpage pe-import">
      <Link className="cp-btn-ghost" to="/user-setup">
        ← Participant Management
      </Link>
      <h1>Bulk Employee Import</h1>
      <p className="pe-muted">
        Columns supported: email, name, employee_id, role, manager, department, business_unit,
        territory, compensation_plan / plan, quota / personal_target, effective_date.
      </p>

      <ol className="pe-steps">
        {STEPS.map((label, idx) => (
          <li key={label} className={idx === step ? "is-active" : idx < step ? "is-done" : ""}>
            {label}
          </li>
        ))}
      </ol>

      <div className="panel">
        <label className="form-field">
          CSV file
          <input
            type="file"
            accept=".csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setValidation(null);
              setStep(0);
            }}
          />
        </label>
        {file ? <p className="pe-muted">Selected: {file.name}</p> : null}

        <div className="pe-tab__actions">
          <button type="button" className="btn-secondary" disabled={!file || busy} onClick={validate}>
            {busy && step < 2 ? "Validating…" : "Validate"}
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!file || busy || (validation && validation.error_count > 0)}
            onClick={importFile}
          >
            {busy && step >= 2 ? "Importing…" : "Import"}
          </button>
        </div>

        {validation ? (
          <div className="pe-import-result">
            <dl className="pe-overview-grid">
              <div>
                <dt>Total rows</dt>
                <dd>{validation.total_rows}</dd>
              </div>
              <div>
                <dt>Valid</dt>
                <dd>{validation.valid_rows}</dd>
              </div>
              <div>
                <dt>Errors</dt>
                <dd>{validation.error_count}</dd>
              </div>
              <div>
                <dt>Warnings</dt>
                <dd>{validation.warning_count}</dd>
              </div>
            </dl>

            {(validation.errors || []).length > 0 ? (
              <>
                <h3>Errors</h3>
                <ul className="pe-import-errors">
                  {validation.errors.slice(0, 20).map((e, i) => (
                    <li key={`${e.row}-${i}`}>
                      Row {e.row}: {e.error}
                      {e.email ? ` (${e.email})` : ""}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {(validation.warnings || []).length > 0 ? (
              <>
                <h3>Warnings</h3>
                <ul className="pe-import-errors pe-import-errors--warn">
                  {validation.warnings.slice(0, 15).map((w, i) => (
                    <li key={`${w.row}-${i}`}>
                      Row {w.row}: {w.warning}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            <h3>Preview</h3>
            <div className="pe-grid__wrap">
              <table className="pe-mini-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Employee ID</th>
                    <th>Role</th>
                    <th>Plan</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(validation.preview || []).slice(0, 25).map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      <td>{row.name || "—"}</td>
                      <td>{row.email}</td>
                      <td>{row.employee_id || "—"}</td>
                      <td>{row.role || "—"}</td>
                      <td>{row.plan || "—"}</td>
                      <td>{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <h2>Import history</h2>
        {history.length === 0 ? (
          <p className="pe-muted">No employee imports yet.</p>
        ) : (
          <table className="pe-mini-table">
            <thead>
              <tr>
                <th>When</th>
                <th>File</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Success</th>
                <th>Failed</th>
                <th>By</th>
              </tr>
            </thead>
            <tbody>
              {history.map((job) => (
                <tr key={job.id}>
                  <td>{job.created_at ? new Date(job.created_at).toLocaleString() : "—"}</td>
                  <td>{job.filename || "—"}</td>
                  <td>{job.status}</td>
                  <td>{job.row_count}</td>
                  <td>{job.success ?? "—"}</td>
                  <td>{job.failed ?? "—"}</td>
                  <td>{job.created_by || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default PeopleImportPage;
