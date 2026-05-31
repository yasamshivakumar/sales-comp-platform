import { useRef, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";

function OrderUpload({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);
  const { success, error, warning } = useToast();

  const pickFile = (selected) => {
    if (!selected) return;
    if (!selected.name.endsWith(".csv")) {
      warning("Please select a CSV file");
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
        if (result?.errors?.length) {
          console.warn("Upload errors:", result.errors);
        }
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
      warning("Select a CSV file first");
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
        success(`Upload done — ${res.data.success} succeeded, ${res.data.failed} failed`);
        if (res.data.errors?.length) {
          console.warn("Upload errors:", res.data.errors);
        }
      }
      setFile(null);
      onUploadSuccess();
    } catch (err) {
      error(err.response?.data?.error || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="panel">
      <div className="orders-section__head">
        <div className="orders-section__icon">📤</div>
        {/* <div>
          <h3 className="orders-section__title">Bulk upload</h3>
          <p className="orders-section__desc">Import many orders from CSV at once</p>
        </div> */}
      </div>

      <div
        className={`upload-zone${dragOver ? " upload-zone--active" : ""}`}
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
        <div className="upload-zone__icon">📁</div>
        <p className="upload-zone__text">
          {file ? "Click to replace file" : "Drop CSV here or click to browse"}
        </p>
        <p className="upload-zone__hint">
          Required columns: order_id, order_date, employee_id, sales_amount. Optional: position_name, etc.
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
          📄 {file.name}
          <span style={{ opacity: 0.7 }}>
            ({(file.size / 1024).toFixed(1)} KB)
          </span>
        </div>
      )}

      <div className="form-actions">
        <button
          type="button"
          className="btn-success"
          onClick={uploadOrders}
          disabled={!file || uploading}
        >
          {uploading ? "Uploading…" : "Upload CSV"}
        </button>
        <a href="/orders_template.csv" download className="btn-secondary" style={{ textDecoration: "none" }}>
          Download template
        </a>
      </div>
    </div>
  );
}

export default OrderUpload;
