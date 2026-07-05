import { useRef, useState } from "react";
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

function OrderUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);
  const { success, error, warning } = useToast();

  const pickFile = (selected) => {
    if (!selected) return;
    if (!selected.name.endsWith(".csv")) {
      warning({ title: "Invalid file", message: "Please select a CSV file to import orders." });
      return;
    }
    setFile(selected);
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
    warning("Import still running — refresh orders in a minute");
    return false;
  };

  const uploadOrders = async () => {
    if (!file) {
      warning({ title: "No file selected", message: "Choose a CSV file before running the import." });
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api.post("orders-upload/", formData);
      if (res.status === 202 && res.data.async && res.data.job_id) {
        success(`Large file queued (${res.data.row_count} rows). Processing…`);
        await pollImportJob(res.data.job_id);
      } else {
        const created = res.data.commissions_created ?? 0;
        const skipped = res.data.commissions_skipped ?? 0;
        const warnDetail = res.data.commission_warnings?.[0]?.reason;

        if (warnDetail) {
          warning({
            title: "Commission not calculated",
            message: warnDetail,
          });
        } else if (skipped > 0) {
          warning({
            title: "Partial import",
            message: `${skipped} order(s) were saved without a commission. Orders import as Booked — mark Success in the Order queue when ready (same workflow as CRM sync).`,
          });
        } else {
          success({
            title: "Import complete",
            message: `${res.data.success} order(s) imported with ${created} commission(s) created.`,
          });
        }

        if (res.data.errors?.length) {
          const firstErrors = res.data.errors.slice(0, 3);
          const detail = firstErrors
            .map((item) => `Row ${item.row}: ${item.error}`)
            .join(" · ");
          warning({
            title: `${res.data.failed} row(s) failed to import`,
            message: detail,
          });
        }
      }
      setFile(null);
      onUploadSuccess?.();
    } catch (err) {
      error({
        title: "Upload failed",
        message: err.response?.data?.error || "The order file could not be processed. Try again.",
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="orders-panel">
      <div className="orders-panel__header">
        <div>
          <h2 className="orders-panel__title">Import orders</h2>
        </div>
      </div>

      <div className="orders-upload-layout">
        <div>
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
              Supports order_id, order_date, employee_id, sales_amount and optional columns.
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              onChange={(e) => pickFile(e.target.files[0])}
            />
          </div>

          {file && (
            <div className="file-chip">
              {file.name}
              <span style={{ opacity: 0.7 }}>
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
            </div>
          )}

          <div className="orders-form-actions" style={{ borderTop: "none", marginTop: 16 }}>
            <button
              type="button"
              className="btn-primary"
              onClick={uploadOrders}
              disabled={!file || uploading}
            >
              {uploading ? "Uploading…" : "Run import"}
            </button>
            <a
              href="/orders_template.csv"
              download
              className="btn-secondary"
              style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
            >
              Download template
            </a>
          </div>
        </div>

        <aside className="orders-upload-side">
          <h4>File requirements</h4>
          <ul>
            <li>UTF-8 CSV format</li>
            <li>Header row required</li>
            <li>order_id must be unique per org</li>
            <li>Dates: YYYY-MM-DD</li>
          </ul>
          <h4>Required columns</h4>
          <ul>
            <li>order_id</li>
            <li>order_date</li>
            <li>employee_id</li>
            <li>sales_amount</li>
          </ul>
          <h4>Optional</h4>
          <ul>
            <li>position_name</li>
            <li>service_name</li>
            <li>order_status (Booked until closed; use Success to generate commission)</li>
            <li>currency (USD, INR, AUD, EUR — sets business group automatically when blank)</li>
            <li>business_group (optional — India, USA, Australia, Europe)</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}

export default OrderUpload;
