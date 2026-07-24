import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { formatMoney } from "../utils/currency";
import "./analytics.css";

const STEPS = [
  "Data source",
  "Fields",
  "Filters",
  "Grouping",
  "Sorting",
  "Visualization",
  "Save",
];

const emptyDef = {
  name: "",
  description: "",
  report_type: "",
  fields: [],
  filters: [],
  group_by: "",
  sort_by: "",
  sort_dir: "desc",
  visualization: "table",
  visibility: "private",
};

function ReportBuilder() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const editId = params.get("id");
  const [step, setStep] = useState(0);
  const [datasources, setDatasources] = useState([]);
  const [def, setDef] = useState(emptyDef);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const dsRes = await api.get("analytics/datasources/");
        if (cancelled) return;
        setDatasources(dsRes.data.results || []);
        if (editId) {
          const r = await api.get(`analytics/reports/${editId}/`);
          if (cancelled) return;
          setDef({
            name: r.data.name || "",
            description: r.data.description || "",
            report_type: r.data.report_type || "",
            fields: r.data.fields || [],
            filters: r.data.filters || [],
            group_by: r.data.group_by || "",
            sort_by: r.data.sort_by || "",
            sort_dir: r.data.sort_dir || "desc",
            visualization: r.data.visualization || "table",
            visibility: r.data.visibility || "private",
          });
          setStep(1);
        }
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err, "Failed to load builder"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [editId]);

  const selectedDs = useMemo(
    () => datasources.find((d) => d.key === def.report_type),
    [datasources, def.report_type]
  );

  const availableFields = selectedDs?.fields || [];
  const selectedKeys = new Set((def.fields || []).map((f) => f.field_key || f.key));

  const toggleField = (field) => {
    setDef((prev) => {
      const keys = new Set((prev.fields || []).map((f) => f.field_key));
      let fields;
      if (keys.has(field.key)) {
        fields = prev.fields.filter((f) => f.field_key !== field.key);
      } else {
        fields = [
          ...prev.fields,
          { field_key: field.key, label: field.label, display_order: prev.fields.length },
        ];
      }
      return { ...prev, fields };
    });
  };

  const runPreview = useCallback(async () => {
    if (!def.report_type || !(def.fields || []).length) {
      setPreview(null);
      return;
    }
    try {
      const res = await api.post("analytics/reports/preview/", {
        ...def,
        limit: 50,
      });
      setPreview(res.data);
      setError("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Preview failed"));
      setPreview(null);
    }
  }, [def]);

  useEffect(() => {
    if (step >= 2 && def.report_type && def.fields.length) {
      const t = setTimeout(runPreview, 300);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [step, def, runPreview]);

  const save = async () => {
    if (!(def.name || "").trim()) {
      setError("Report name is required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      let res;
      if (editId) {
        res = await api.patch(`analytics/reports/${editId}/`, def);
      } else {
        res = await api.post("analytics/reports/", def);
      }
      navigate(`/analytics/reports/${res.data.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  const addFilter = () => {
    const first = availableFields.find((f) => f.filterable !== false);
    if (!first) return;
    setDef((prev) => ({
      ...prev,
      filters: [
        ...prev.filters,
        { field_key: first.key, operator: "contains", value: "" },
      ],
    }));
  };

  if (loading) return <p className="an-muted">Loading builder...</p>;

  return (
    <div className="an-builder">
      <ol className="an-steps">
        {STEPS.map((label, idx) => (
          <li key={label} className={idx === step ? "is-active" : idx < step ? "is-done" : ""}>
            <button type="button" onClick={() => setStep(idx)}>
              <span>{idx + 1}</span>
              {label}
            </button>
          </li>
        ))}
      </ol>

      {error ? <div className="an-error">{error}</div> : null}

      <div className="an-builder-grid">
        <div className="an-panel">
          {step === 0 && (
            <>
              <h2>Select data source</h2>
              <div className="an-source-grid">
                {datasources.map((ds) => (
                  <button
                    key={ds.key}
                    type="button"
                    className={`an-source${def.report_type === ds.key ? " is-selected" : ""}`}
                    onClick={() =>
                      setDef((prev) => ({
                        ...prev,
                        report_type: ds.key,
                        fields: (ds.default_fields || []).map((k, i) => {
                          const f = (ds.fields || []).find((x) => x.key === k);
                          return {
                            field_key: k,
                            label: f?.label || k,
                            display_order: i,
                          };
                        }),
                        sort_by: ds.default_sort || "",
                        filters: [],
                        group_by: "",
                      }))
                    }
                  >
                    <strong>{ds.label}</strong>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h2>Select fields</h2>
              {!selectedDs ? (
                <p className="an-muted">Choose a data source first.</p>
              ) : (
                <div className="an-field-picker">
                  {availableFields.map((f) => (
                    <label key={f.key} className="an-check">
                      <input
                        type="checkbox"
                        checked={selectedKeys.has(f.key)}
                        onChange={() => toggleField(f)}
                      />
                      <span>{f.label}</span>
                      <em>{f.type}</em>
                    </label>
                  ))}
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <h2>Filters</h2>
              <button type="button" className="an-btn" onClick={addFilter}>
                Add filter
              </button>
              {(def.filters || []).map((filt, idx) => (
                <div key={idx} className="an-filter-row">
                  <select
                    value={filt.field_key}
                    onChange={(e) => {
                      const v = e.target.value;
                      setDef((prev) => {
                        const filters = [...prev.filters];
                        filters[idx] = { ...filters[idx], field_key: v };
                        return { ...prev, filters };
                      });
                    }}
                  >
                    {availableFields.map((f) => (
                      <option key={f.key} value={f.key}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={filt.operator}
                    onChange={(e) => {
                      const v = e.target.value;
                      setDef((prev) => {
                        const filters = [...prev.filters];
                        filters[idx] = { ...filters[idx], operator: v };
                        return { ...prev, filters };
                      });
                    }}
                  >
                    <option value="eq">Equals</option>
                    <option value="contains">Contains</option>
                    <option value="gte">≥</option>
                    <option value="lte">≤</option>
                    <option value="between">Between</option>
                  </select>
                  {filt.operator === "between" ? (
                    <>
                      <input
                        placeholder="From"
                        value={filt.value?.from || ""}
                        onChange={(e) => {
                          const v = e.target.value;
                          setDef((prev) => {
                            const filters = [...prev.filters];
                            filters[idx] = {
                              ...filters[idx],
                              value: { ...(filters[idx].value || {}), from: v },
                            };
                            return { ...prev, filters };
                          });
                        }}
                      />
                      <input
                        placeholder="To"
                        value={filt.value?.to || ""}
                        onChange={(e) => {
                          const v = e.target.value;
                          setDef((prev) => {
                            const filters = [...prev.filters];
                            filters[idx] = {
                              ...filters[idx],
                              value: { ...(filters[idx].value || {}), to: v },
                            };
                            return { ...prev, filters };
                          });
                        }}
                      />
                    </>
                  ) : (
                    <input
                      value={typeof filt.value === "object" ? "" : filt.value || ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        setDef((prev) => {
                          const filters = [...prev.filters];
                          filters[idx] = { ...filters[idx], value: v };
                          return { ...prev, filters };
                        });
                      }}
                    />
                  )}
                  <button
                    type="button"
                    className="an-danger"
                    onClick={() =>
                      setDef((prev) => ({
                        ...prev,
                        filters: prev.filters.filter((_, i) => i !== idx),
                      }))
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
            </>
          )}

          {step === 3 && (
            <>
              <h2>Grouping</h2>
              <select
                value={def.group_by}
                onChange={(e) => setDef((p) => ({ ...p, group_by: e.target.value }))}
              >
                <option value="">No grouping</option>
                {availableFields
                  .filter((f) => f.groupable)
                  .map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.label}
                    </option>
                  ))}
              </select>
            </>
          )}

          {step === 4 && (
            <>
              <h2>Sorting</h2>
              <div className="an-filter-row">
                <select
                  value={def.sort_by}
                  onChange={(e) => setDef((p) => ({ ...p, sort_by: e.target.value }))}
                >
                  <option value="">Default</option>
                  {availableFields.map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.label}
                    </option>
                  ))}
                </select>
                <select
                  value={def.sort_dir}
                  onChange={(e) => setDef((p) => ({ ...p, sort_dir: e.target.value }))}
                >
                  <option value="desc">Highest / newest first</option>
                  <option value="asc">Lowest / oldest first</option>
                </select>
              </div>
            </>
          )}

          {step === 5 && (
            <>
              <h2>Visualization</h2>
              <div className="an-source-grid">
                {[
                  ["table", "Table"],
                  ["bar", "Bar chart"],
                  ["line", "Line chart"],
                  ["pie", "Pie chart"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={`an-source${def.visualization === value ? " is-selected" : ""}`}
                    onClick={() => setDef((p) => ({ ...p, visualization: value }))}
                  >
                    <strong>{label}</strong>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 6 && (
            <>
              <h2>Save report</h2>
              <label className="an-label">
                Report name
                <input
                  className="an-input"
                  value={def.name}
                  onChange={(e) => setDef((p) => ({ ...p, name: e.target.value }))}
                />
              </label>
              <label className="an-label">
                Description
                <textarea
                  className="an-input"
                  rows={3}
                  value={def.description}
                  onChange={(e) => setDef((p) => ({ ...p, description: e.target.value }))}
                />
              </label>
              <label className="an-label">
                Visibility
                <select
                  value={def.visibility}
                  onChange={(e) => setDef((p) => ({ ...p, visibility: e.target.value }))}
                >
                  <option value="private">Private</option>
                  <option value="organization">Organization</option>
                  <option value="role">Role-restricted</option>
                </select>
              </label>
            </>
          )}

          <div className="an-wizard-nav">
            <button
              type="button"
              className="an-btn"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
            >
              Back
            </button>
            {step < STEPS.length - 1 ? (
              <button
                type="button"
                className="an-btn an-btn--primary"
                disabled={step === 0 && !def.report_type}
                onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                className="an-btn an-btn--primary"
                disabled={saving}
                onClick={save}
              >
                {saving ? "Saving..." : editId ? "Update report" : "Save report"}
              </button>
            )}
          </div>
        </div>

        <aside className="an-panel an-preview">
          <div className="an-toolbar">
            <h2>Preview</h2>
            <button type="button" className="an-btn" onClick={runPreview}>
              Refresh
            </button>
          </div>
          {!preview ? (
            <p className="an-muted">Select fields to preview live data.</p>
          ) : (
            <div className="an-table-wrap">
              <table className="an-table">
                <thead>
                  <tr>
                    {(preview.columns || []).map((c) => (
                      <th key={c.key}>{c.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(preview.rows || []).slice(0, 20).map((row, idx) => (
                    <tr key={idx}>
                      {(preview.columns || []).map((c) => (
                        <td key={c.key}>
                          {c.type === "number" && row[c.key] != null
                            ? formatMoney(row[c.key], "INR", { compact: true })
                            : row[c.key] ?? "-"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="an-muted">{preview.count} rows (preview capped)</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

export default ReportBuilder;
