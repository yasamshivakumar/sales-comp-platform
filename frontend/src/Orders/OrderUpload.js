import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { useToast } from "../Components/Toast";

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

const STEPS = ["Upload", "Validate", "Preview", "Import"];

/**
 * Enterprise CSV import wizard:
 * Upload → Validate → Preview / Errors → Import
 */
function OrderUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [step, setStep] = useState(0);
  const [validation, setValidation] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);
  const { success, error, warning } = useToast();
  const MAX_UPLOAD_MB = 10;

  const pickFile = (selected) => {
    if (!selected) return;
    if (!selected.name.endsWith(".csv")) {
      warning({ title: "Invalid file", message: "Please select a CSV file." });
      return;
    }
    if (selected.size > MAX_UPLOAD_MB * 1024 * 1024) {
      warning({
        title: "File too large",
        message: `CSV imports are limited to ${MAX_UPLOAD_MB} MB.`,
      });
      return;
    }
    setFile(selected);
    setValidation(null);
    setStep(0);
  };

  const validateFile = async () => {
    if (!file) {
      warning("Choose a CSV file first");
      return;
    }
    setValidating(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("orders-upload/validate/", formData);
      setValidation(res.data);
      setStep(res.data.error_count ? 1 : 2);
      if (res.data.error_count) {
        warning(`${res.data.error_count} validation issue(s) found`);
      } else {
        success(`${res.data.preview_count} row(s) ready to import`);
      }
    } catch (err) {
      error(err.response?.data?.error || "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  const pollImportJob = async (jobId) => {
    const maxAttempts = 120;
    for (let i = 0; i < maxAttempts; i += 1) {
      await new Promise((r) => setTimeout(r, 2000));
      const statusRes = await api.get(`import-jobs/${jobId}/`);
      const { status, result, error_message: errMsg } = statusRes.data;
      if (status === "completed") {
        success(
          `Import finished — ${result?.success ?? 0} succeeded, ${result?.failed ?? 0} failed`
        );
        return true;
      }
      if (status === "failed") {
        error(errMsg || "Background import failed");
        return false;
      }
    }
    warning("Import still running — refresh orders shortly");
    return false;
  };

  const uploadOrders = async () => {
    if (!file) return;
    setUploading(true);
    setStep(3);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("orders-upload/", formData);
      if (res.status === 202 && res.data.async && res.data.job_id) {
        success(`Large file queued (${res.data.row_count} rows). Processing…`);
        await pollImportJob(res.data.job_id);
      } else {
        if (res.data.errors?.length) {
          warning({
            title: `${res.data.failed} row(s) failed`,
            message: res.data.errors
              .slice(0, 3)
              .map((item) => `Row ${item.row}: ${item.error}`)
              .join(" · "),
          });
        } else {
          success(`${res.data.success} order(s) imported`);
        }
      }
      setFile(null);
      setValidation(null);
      setStep(0);
      onUploadSuccess?.();
    } catch (err) {
      error({
        title: "Upload failed",
        message: err.response?.data?.error || "Could not process file",
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="tx-import">
      <div className="tx-import__head">
        <div>
          <Link className="cp-btn-ghost" to="/orders">
            ← Orders
          </Link>
          <h1>Import Orders</h1>
          <p className="tx-muted">Upload → Validate → Preview → Import</p>
        </div>
        <a href="/orders_template.csv" download className="btn-secondary">
          Download template
        </a>
      </div>

      <ol className="tx-import__steps">
        {STEPS.map((label, idx) => (
          <li key={label} className={idx <= step ? "is-active" : ""}>
            {label}
          </li>
        ))}
      </ol>

      <div
        className={`orders-upload-zone${dragOver ? " orders-upload-zone--active" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pickFile(e.dataTransfer.files[0]);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      >
        <div className="orders-upload-zone__icon">
          <UploadIcon />
        </div>
        <p className="orders-upload-zone__title">
          {file ? file.name : "Drop CSV file here or click to browse"}
        </p>
        <p className="orders-upload-zone__hint">
          Required: order_id, order_date, employee_id, sales_amount. Optional: customer_name,
          product_name, region, business_group.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={(e) => pickFile(e.target.files[0])}
        />
      </div>

      <div className="tx-import__actions">
        <button
          type="button"
          className="btn-secondary"
          disabled={!file || validating || uploading}
          onClick={validateFile}
        >
          {validating ? "Validating…" : "Validate data"}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={!file || uploading || (validation && validation.error_count > 0)}
          onClick={uploadOrders}
        >
          {uploading ? "Importing…" : "Import orders"}
        </button>
      </div>

      {validation?.errors?.length ? (
        <div className="tx-import__errors">
          <h3>Validation errors</h3>
          <ul>
            {validation.errors.slice(0, 40).map((err) => (
              <li key={`${err.row}-${err.order_id}`}>
                Row {err.row} ({err.order_id}): {(err.errors || []).join(", ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {validation?.preview?.length ? (
        <div className="tx-import__preview">
          <h3>Preview ({validation.preview_count} valid)</h3>
          <div className="tx-grid__wrap">
            <table className="tx-table">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Order ID</th>
                  <th>Employee</th>
                  <th>Customer</th>
                  <th>Product</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {validation.preview.map((row) => (
                  <tr key={`${row.row}-${row.order_id}`}>
                    <td>{row.row}</td>
                    <td>{row.order_id}</td>
                    <td>{row.employee_id}</td>
                    <td>{row.customer_name || "—"}</td>
                    <td>{row.product_name || "—"}</td>
                    <td>{row.sales_amount}</td>
                    <td>{row.order_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default OrderUpload;
