import api from "../../api";

/** Shared config adapters for Orders / People enterprise ImportDrawer. */

export const ORDERS_IMPORT_CONFIG = {
  title: "Import Orders",
  description:
    "Upload a CSV of sales orders. Validate first, then import. Large files may process in the background.",
  templateUrl: "/orders_template.csv",
  templateLabel: "Download CSV template",
  requiredColumns: [
    "order_id",
    "order_date",
    "employee_id",
    "sales_amount",
  ],
  maxSizeMb: 10,
  async validateFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await api.post("orders-upload/validate/", formData);
    return res.data;
  },
  async importFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await api.post("orders-upload/", formData);
    if (res.status === 202 && res.data?.async && res.data?.job_id) {
      const jobId = res.data.job_id;
      const maxAttempts = 120;
      for (let i = 0; i < maxAttempts; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        const statusRes = await api.get(`import-jobs/${jobId}/`);
        const { status, result, error_message: errMsg } = statusRes.data;
        if (status === "completed") {
          return {
            success: result?.success ?? 0,
            failed: result?.failed ?? 0,
            skipped: result?.skipped ?? 0,
            errors: result?.errors || [],
            async: true,
          };
        }
        if (status === "failed") {
          const err = new Error(errMsg || "Background import failed");
          throw err;
        }
      }
      return {
        success: 0,
        failed: 0,
        skipped: 0,
        errors: [{ row: "", error: "Import still running — refresh Orders shortly." }],
        pending: true,
      };
    }
    return res.data;
  },
  normalizeValidation(data) {
    const errors = (data.errors || []).map((err) => ({
      row: err.row,
      message:
        (Array.isArray(err.errors) ? err.errors.join(", ") : err.error || err.message || "") +
        (err.order_id ? ` (${err.order_id})` : ""),
    }));
    const total =
      data.total_rows ??
      (data.preview_count || 0) + (data.error_count || 0);
    return {
      totalRows: total,
      validRows: data.valid_rows ?? data.preview_count ?? 0,
      errorCount: data.error_count ?? errors.length,
      warningCount: data.warning_count ?? 0,
      errors,
      warnings: data.warnings || [],
      missingColumns: data.missing_columns || data.missingColumns || [],
      preview: data.preview || [],
      previewColumns: [
        "row",
        "order_id",
        "employee_id",
        "customer_name",
        "product_name",
        "sales_amount",
        "order_status",
      ],
    };
  },
  normalizeResult(data) {
    const errors = (data.errors || []).map((err) => ({
      row: err.row,
      message: err.error || err.message || (err.errors || []).join(", "),
    }));
    return {
      imported: data.success ?? data.imported ?? 0,
      skipped: data.skipped ?? 0,
      failed: data.failed ?? errors.length,
      errors,
    };
  },
};

export const PEOPLE_IMPORT_CONFIG = {
  title: "Import Employees",
  description:
    "Upload a CSV of participants. Validate first to catch missing fields and duplicates, then import.",
  templateUrl: "/user_setup_template.csv",
  templateLabel: "Download employee template",
  requiredColumns: ["email", "name", "employee_id", "role"],
  maxSizeMb: 10,
  async validateFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await api.post("user-setup-upload/validate/", formData);
    return res.data;
  },
  async importFile(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await api.post("user-setup-upload/", formData);
    return res.data;
  },
  normalizeValidation(data) {
    const errors = (data.errors || []).map((err) => ({
      row: err.row,
      message:
        (err.error || err.message || "") + (err.email ? ` (${err.email})` : ""),
    }));
    return {
      totalRows: data.total_rows ?? 0,
      validRows: data.valid_rows ?? 0,
      errorCount: data.error_count ?? errors.length,
      warningCount: data.warning_count ?? 0,
      errors,
      warnings: (data.warnings || []).map((w) => ({
        row: w.row,
        message: w.warning || w.message,
      })),
      missingColumns: data.missing_columns || data.missingColumns || [],
      preview: data.preview || [],
      previewColumns: [
        "row",
        "name",
        "email",
        "employee_id",
        "role",
        "plan",
        "status",
      ],
    };
  },
  normalizeResult(data) {
    if (data?.job_id && (data.success == null && data.imported == null)) {
      return {
        imported: data.row_count ?? 0,
        skipped: 0,
        failed: 0,
        errors: [],
      };
    }
    const errors = (data.errors || []).map((err) => ({
      row: err.row,
      message: err.error || err.message || "",
    }));
    return {
      imported: data.success ?? data.imported ?? 0,
      skipped: data.skipped ?? 0,
      failed: data.failed ?? 0,
      errors,
    };
  },
};
