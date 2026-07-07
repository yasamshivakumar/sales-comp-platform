import { useRef, useState } from "react";

function BulkUploadSection({ file, setFile, uploadUsers }) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const pickFile = (selected) => {
    if (!selected) return;
    setFile(selected);
  };

  const handleUpload = async () => {
    setUploading(true);
    try {
      await uploadUsers();
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="orders-section__head" style={{ marginBottom: 16 }}>
        <div className="orders-section__icon">📤</div>
        <div>
          <h3 className="orders-section__title">Bulk import</h3>
          <p className="orders-section__desc">
            CSV required columns: email, role, employee_id, name. Optional columns include
            territory (code or id), business_group, hire_date, and more — see the template.
          </p>
        </div>
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
          {file ? "Click to replace file" : "Drop file here or click to browse"}
        </p>
        <p className="upload-zone__hint">Supports CSV and Excel formats</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={(e) => pickFile(e.target.files[0])}
        />
      </div>

      {file && (
        <div className="file-chip">
          📄 {file.name}
          <span style={{ opacity: 0.7 }}>({(file.size / 1024).toFixed(1)} KB)</span>
        </div>
      )}

      <div className="form-actions">
        <button
          type="button"
          className="btn-success"
          onClick={handleUpload}
          disabled={!file || uploading}
        >
          {uploading ? "Uploading…" : "Upload file"}
        </button>
        <a
          href="/user_setup_template.csv"
          download
          className="btn-secondary"
          style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
        >
          Download template
        </a>
      </div>
    </div>
  );
}

export default BulkUploadSection;
