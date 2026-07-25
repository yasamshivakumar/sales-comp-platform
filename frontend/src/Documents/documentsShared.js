import { useEffect, useState } from "react";
import api, { getApiErrorMessage, getAuthToken } from "../api";
import DatePickerField from "../Components/DatePickerField";
import { ChromeButton } from "../Components/layout/PageChrome";
import { useToast } from "../Components/Toast";

export const DOC_TYPES = [
  { value: "compensation_plan", label: "Compensation Plan" },
  { value: "commission_policy", label: "Commission Policy" },
  { value: "quota_letter", label: "Quota Document" },
  { value: "approval_document", label: "Approval Record" },
  { value: "employee_agreement", label: "Employee Agreement" },
  { value: "exception_approval", label: "Exception Approval" },
  { value: "other", label: "Other" },
];

export const LIFECYCLE = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "pending_review", label: "Pending Review" },
  { value: "approved", label: "Approved" },
  { value: "published", label: "Published" },
  { value: "expired", label: "Expired" },
  { value: "archived", label: "Archived" },
];

export const CATEGORY_META = [
  { key: "compensation_plan", label: "Compensation Plans", hint: "Plan PDFs & packets" },
  { key: "commission_policy", label: "Commission Policies", hint: "Rate & eligibility rules" },
  { key: "quota_letter", label: "Quota Documents", hint: "Targets & assignments" },
  { key: "approval_document", label: "Approval Records", hint: "Sign-offs & letters" },
  { key: "employee_agreement", label: "Employee Agreements", hint: "Participant acknowledgements" },
  { key: "exception_approval", label: "Exception Approvals", hint: "One-off overrides" },
];

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function formatMonthYear(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function periodLabel(doc) {
  const from = doc.effective_from || doc.current_version?.effective_from;
  const to = doc.effective_to || doc.current_version?.effective_to;
  if (!from && !to) return "—";
  return `${formatMonthYear(from) || "…"} – ${formatMonthYear(to) || "…"}`;
}

export function statusBadge(status) {
  const label = (status || "—").replace(/_/g, " ");
  return <span className={`cdr-badge status-${status || "draft"}`}>{label}</span>;
}

export function approvalBadge(status) {
  const label = (status || "not_started").replace(/_/g, " ");
  return <span className={`cdr-badge approval-${status || "not_started"}`}>{label}</span>;
}

export async function fetchDocumentBlob(docId, { versionId, inline, reason } = {}) {
  const path = versionId
    ? `documents/${docId}/versions/${versionId}/download/`
    : `documents/${docId}/download/`;
  const params = new URLSearchParams();
  if (inline) params.set("inline", "1");
  if (reason) params.set("reason", reason);
  const qs = params.toString() ? `?${params}` : "";
  const token = getAuthToken();
  const base = (api.defaults.baseURL || "/api/").replace(/\/?$/, "/");
  const res = await fetch(`${base}${path}${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Download failed");
  return res.blob();
}

export function UploadWizard({ open, onClose, onSaved, plans, people, rules, initial, asTemplate }) {
  const { success, error } = useToast();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "",
    document_type: "compensation_plan",
    related_plan: "",
    linked_rules: [],
    business_unit: "",
    effective_start_date: "",
    effective_end_date: "",
    version_number: "v1",
    description: "",
    approval_required: true,
    approver: "",
    publish: true,
    file: null,
  });

  useEffect(() => {
    if (!open) return;
    setStep(1);
    setForm({
      name: initial?.name || (asTemplate ? "Compensation Policy Template" : ""),
      document_type: initial?.document_type || "compensation_plan",
      related_plan: initial?.related_plan_id || "",
      linked_rules: initial?.linked_rule_ids || [],
      business_unit: initial?.business_unit || "",
      effective_start_date: "",
      effective_end_date: "",
      version_number: initial ? `v${(initial.current_version?.version_number || 1) + 1}` : "v1",
      description: asTemplate ? "Governance template — attach final file before publish." : "",
      approval_required: true,
      approver: "",
      publish: !asTemplate,
      file: null,
    });
  }, [open, initial, asTemplate]);

  if (!open) return null;

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const planRules = (rules || []).filter(
    (r) => !form.related_plan || String(r.compensation_plan || r.compensation_plan_id) === String(form.related_plan)
  );

  const validateStep = () => {
    if (step === 1 && !form.name.trim()) {
      error({ title: "Name required", message: "Enter a document name." });
      return false;
    }
    if (step === 2 && !initial && !asTemplate && !form.file) {
      error({ title: "File required", message: "Upload a PDF, DOCX, XLSX, or CSV." });
      return false;
    }
    if (step === 2 && initial && !form.file) {
      error({ title: "File required", message: "Upload the new version file." });
      return false;
    }
    return true;
  };

  const submit = async () => {
    if (!validateStep()) return;
    setSaving(true);
    try {
      const fd = new FormData();
      const fields = {
        name: form.name,
        document_type: form.document_type,
        related_plan: form.related_plan,
        business_unit: form.business_unit,
        effective_start_date: form.effective_start_date,
        effective_end_date: form.effective_end_date,
        version_number: form.version_number,
        description: form.description,
        approval_required: form.approval_required ? "true" : "false",
        approver_email: form.approver,
        publish: form.publish ? "true" : "false",
        as_template: asTemplate && !form.file ? "true" : "false",
        linked_rules: (form.linked_rules || []).join(","),
      };
      Object.entries(fields).forEach(([k, v]) => {
        if (v === "" || v == null) return;
        fd.append(k, v);
      });
      if (form.file) fd.append("file", form.file);

      if (initial?.id) {
        await api.post(`documents/${initial.id}/versions/`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        success({ title: "Version published", message: "New version is now current." });
      } else {
        await api.post("documents/", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        success({
          title: asTemplate ? "Template created" : "Document registered",
          message: form.publish
            ? "Document entered the compliance workflow."
            : "Saved as draft for later publish.",
        });
      }
      onSaved?.();
      onClose?.();
    } catch (err) {
      error({ title: "Upload failed", message: getApiErrorMessage(err, "Try again.") });
    } finally {
      setSaving(false);
    }
  };

  const steps = [
    { n: 1, label: "Information" },
    { n: 2, label: "Upload" },
    { n: 3, label: "Approval" },
    { n: 4, label: "Review" },
  ];

  return (
    <div className="cdr-modal" role="dialog" aria-modal="true">
      <div className="cdr-modal__backdrop" onClick={onClose} />
      <div className="cdr-modal__panel cdr-wizard">
        <header>
          <div>
            <p className="cdr-eyebrow">Compliance registration</p>
            <h2>
              {initial ? "Upload New Version" : asTemplate ? "Create Document Template" : "Register Document"}
            </h2>
          </div>
          <button type="button" className="cdr-icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <nav className="cdr-wizard__steps" aria-label="Wizard steps">
          {steps.map((s) => (
            <button
              key={s.n}
              type="button"
              className={`cdr-wizard__step ${step === s.n ? "is-active" : ""} ${step > s.n ? "is-done" : ""}`}
              onClick={() => setStep(s.n)}
            >
              <span>{s.n}</span>
              {s.label}
            </button>
          ))}
        </nav>
        <div className="cdr-modal__body">
          {step === 1 ? (
            <>
              <label>
                Document Name *
                <input value={form.name} onChange={(e) => set("name", e.target.value)} disabled={Boolean(initial)} />
              </label>
              <label>
                Category *
                <select
                  value={form.document_type}
                  onChange={(e) => set("document_type", e.target.value)}
                  disabled={Boolean(initial)}
                >
                  {DOC_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Linked Compensation Plan
                <select
                  value={form.related_plan}
                  onChange={(e) => set("related_plan", e.target.value)}
                  disabled={Boolean(initial)}
                >
                  <option value="">None</option>
                  {(plans || []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.plan_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Linked Commission Rules
                <select
                  multiple
                  value={form.linked_rules.map(String)}
                  onChange={(e) =>
                    set(
                      "linked_rules",
                      Array.from(e.target.selectedOptions).map((o) => o.value)
                    )
                  }
                  size={Math.min(5, Math.max(3, planRules.length || 3))}
                >
                  {planRules.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Business Unit
                <input value={form.business_unit} onChange={(e) => set("business_unit", e.target.value)} />
              </label>
              <div className="cdr-modal__row">
                <label>
                  Effective From
                  <DatePickerField
                    label="Effective From"
                    hideLabel
                    value={form.effective_start_date}
                    onChange={(value) => set("effective_start_date", value)}
                    maxDate={form.effective_end_date || undefined}
                  />
                </label>
                <label>
                  Effective To
                  <DatePickerField
                    label="Effective To"
                    hideLabel
                    value={form.effective_end_date}
                    onChange={(value) => set("effective_end_date", value)}
                    minDate={form.effective_start_date || undefined}
                  />
                </label>
              </div>
            </>
          ) : null}
          {step === 2 ? (
            <>
              <label>
                Version Label
                <input value={form.version_number} onChange={(e) => set("version_number", e.target.value)} />
              </label>
              <label>
                File {asTemplate ? "(optional for template)" : "*"}
                <input
                  type="file"
                  accept=".pdf,.docx,.xlsx,.csv,application/pdf"
                  onChange={(e) => set("file", e.target.files?.[0] || null)}
                />
              </label>
              <label>
                Description / Change Reason
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) => set("description", e.target.value)}
                />
              </label>
            </>
          ) : null}
          {step === 3 ? (
            <>
              <label className="cdr-check">
                <input
                  type="checkbox"
                  checked={form.approval_required}
                  onChange={(e) => set("approval_required", e.target.checked)}
                />
                Approval required before Published
              </label>
              <label>
                Approver
                <select
                  value={form.approver}
                  onChange={(e) => set("approver", e.target.value)}
                  disabled={!form.approval_required}
                >
                  <option value="">Select approver</option>
                  {(people || []).map((p) => (
                    <option key={p.id || p.email} value={p.email}>
                      {p.name || `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.email}
                      {p.role ? ` (${p.role})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          {step === 4 ? (
            <div className="cdr-review">
              <dl>
                <div>
                  <dt>Name</dt>
                  <dd>{form.name || "—"}</dd>
                </div>
                <div>
                  <dt>Category</dt>
                  <dd>{DOC_TYPES.find((t) => t.value === form.document_type)?.label}</dd>
                </div>
                <div>
                  <dt>Plan</dt>
                  <dd>
                    {plans.find((p) => String(p.id) === String(form.related_plan))?.plan_name || "—"}
                  </dd>
                </div>
                <div>
                  <dt>Rules</dt>
                  <dd>{form.linked_rules.length || "None"}</dd>
                </div>
                <div>
                  <dt>Approval</dt>
                  <dd>{form.approval_required ? "Required" : "Not required"}</dd>
                </div>
              </dl>
              {!initial ? (
                <label className="cdr-check">
                  <input
                    type="checkbox"
                    checked={form.publish}
                    onChange={(e) => set("publish", e.target.checked)}
                  />
                  Submit to workflow (uncheck to keep Draft)
                </label>
              ) : null}
            </div>
          ) : null}
        </div>
        <footer>
          <ChromeButton type="button" onClick={onClose}>
            Cancel
          </ChromeButton>
          <div className="cdr-wizard__nav">
            {step > 1 ? (
              <ChromeButton type="button" onClick={() => setStep((s) => s - 1)}>
                Back
              </ChromeButton>
            ) : null}
            {step < 4 ? (
              <button
                type="button"
                className="pg-btn pg-btn--primary"
                onClick={() => {
                  if (validateStep()) setStep((s) => Math.min(4, s + 1));
                }}
              >
                Continue
              </button>
            ) : (
              <button type="button" className="pg-btn pg-btn--primary" disabled={saving} onClick={submit}>
                {saving ? "Saving…" : initial ? "Publish Version" : form.publish ? "Submit Document" : "Save Draft"}
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
