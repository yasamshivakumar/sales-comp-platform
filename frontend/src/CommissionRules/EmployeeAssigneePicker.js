import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api from "../api";

const PAGE_SIZE = 500;

function initialsFor(person) {
  const source = (person?.name || person?.email || "?").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase() || "?";
}

function matchesSearch(person, query) {
  if (!query) return true;
  const haystack = [person.name, person.email, person.employee_id, person.job_title, person.role]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

/**
 * Plan employee picker:
 * Select compensation plan → load employees assigned to that plan only.
 */
function EmployeeAssigneePicker({
  planId,
  selectedIds = [],
  onChange,
  disabled = false,
  initialPeople = [],
}) {
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [knownById, setKnownById] = useState(() => new Map());
  const loadSeq = useRef(0);

  const selectedSet = useMemo(
    () => new Set((selectedIds || []).map((id) => Number(id))),
    [selectedIds]
  );
  const searchQuery = search.trim().toLowerCase();
  const filteredRows = useMemo(
    () => rows.filter((person) => matchesSearch(person, searchQuery)),
    [rows, searchQuery]
  );

  useEffect(() => {
    if (!initialPeople?.length) return;
    setKnownById((prev) => {
      const next = new Map(prev);
      initialPeople.forEach((row) => {
        if (row?.id != null) next.set(Number(row.id), row);
      });
      return next;
    });
  }, [initialPeople]);

  const loadAllEmployees = useCallback(async (plan) => {
    if (!plan) {
      setRows([]);
      setKnownById(new Map());
      setLoading(false);
      return;
    }
    const requestId = ++loadSeq.current;
    setLoading(true);
    setError("");
    setSearch("");
    setRows([]);
    try {
      let page = 1;
      let hasMore = true;
      const all = [];
      while (hasMore) {
        const params = new URLSearchParams({
          plan_id: String(plan),
          page: String(page),
          page_size: String(PAGE_SIZE),
        });
        const res = await api.get(`commission-rules/eligible-employees/?${params}`);
        if (requestId !== loadSeq.current) return;
        const data = res.data || {};
        const results = Array.isArray(data.results)
          ? data.results
          : Array.isArray(data)
            ? data
            : [];
        all.push(...results);
        hasMore = Boolean(data.has_more);
        page += 1;
        if (page > 40) break;
      }
      if (requestId !== loadSeq.current) return;
      setRows(all);
      setKnownById(() => {
        const next = new Map();
        all.forEach((row) => next.set(Number(row.id), row));
        return next;
      });
    } catch {
      if (requestId !== loadSeq.current) return;
      setRows([]);
      setKnownById(new Map());
      setError("Failed to load employees for this plan.");
    } finally {
      if (requestId === loadSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setSearch("");
    setError("");
    setRows([]);
    if (!planId) {
      setKnownById(new Map());
      setLoading(false);
      return;
    }
    loadAllEmployees(planId);
  }, [planId, loadAllEmployees]);

  const setSelected = (ids) => {
    onChange(Array.from(new Set(ids.map((id) => Number(id)))));
  };

  const toggle = (id) => {
    if (disabled) return;
    const next = new Set(selectedSet);
    const n = Number(id);
    if (next.has(n)) next.delete(n);
    else next.add(n);
    setSelected(Array.from(next));
  };

  const selectedPeople = useMemo(
    () =>
      (selectedIds || []).map(
        (id) => knownById.get(Number(id)) || { id, name: `Employee #${id}` }
      ),
    [selectedIds, knownById]
  );

  if (!planId) {
    return (
      <div className="cr-assignee-empty">
        Select a Compensation Plan to load its employees.
      </div>
    );
  }

  if (loading) {
    return <div className="cr-assignee-empty">Loading employees…</div>;
  }

  if (error) {
    return <div className="cr-assignee-empty cr-hint--warn">{error}</div>;
  }

  if (rows.length === 0) {
    return (
      <div className="cr-assignee-empty">
        No employees match this Compensation Plan for your company. Check People &amp;
        Access that they are on this plan (or have a matching role with no other plan).
      </div>
    );
  }

  return (
    <div className={`cr-assignee ${disabled ? "cr-assignee--disabled" : ""}`}>
      {selectedPeople.length > 0 && (
        <div className="cr-assignee__chips" aria-label="Selected employees">
          {selectedPeople.map((person) => {
            const id = Number(person.id);
            return (
              <button
                key={id}
                type="button"
                className="cr-employee-chip"
                title="Remove"
                disabled={disabled}
                onClick={() => toggle(id)}
              >
                <span className="cr-employee-chip__avatar" aria-hidden>
                  {initialsFor(person)}
                </span>
                <span>
                  {person.name || person.email || `Employee #${id}`}
                  {person.employee_id ? ` · ${person.employee_id}` : ""}
                </span>
                <span className="cr-employee-chip__x" aria-hidden>
                  ×
                </span>
              </button>
            );
          })}
        </div>
      )}

      <div className="cr-assignee__sticky">
        <div className="cr-assignee__meta">
          <span>
            {rows.length} employee{rows.length === 1 ? "" : "s"} loaded
          </span>
          <span className="cr-assignee__meta-sep">·</span>
          <span>{selectedSet.size} selected</span>
          {searchQuery ? (
            <>
              <span className="cr-assignee__meta-sep">·</span>
              <span>{filteredRows.length} match</span>
            </>
          ) : null}
        </div>
        <div className="cr-assignee__toolbar">
          <input
            type="search"
            className="cr-employee-search"
            placeholder="Search employees by name, ID, or email…"
            value={search}
            disabled={disabled}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search employees"
          />
          <button
            type="button"
            className="btn-secondary"
            disabled={disabled || filteredRows.length === 0}
            onClick={() => setSelected(filteredRows.map((p) => Number(p.id)))}
          >
            Select all{searchQuery ? " matching" : ""}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={disabled || selectedSet.size === 0}
            onClick={() => setSelected([])}
          >
            Clear
          </button>
        </div>
      </div>

      <ul className="cr-assignee__list-simple">
        {filteredRows.length === 0 ? (
          <li className="cr-assignee-empty">No employees match “{search.trim()}”.</li>
        ) : (
          filteredRows.map((person) => {
            const id = Number(person.id);
            const checked = selectedSet.has(id);
            return (
              <li key={id}>
                <label className={`cr-assignee__row ${checked ? "is-selected" : ""}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => toggle(id)}
                  />
                  <span className="cr-assignee__avatar" aria-hidden>
                    {initialsFor(person)}
                  </span>
                  <span className="cr-assignee__identity">
                    <span className="cr-assignee__name">
                      {person.name || person.email || `Employee #${id}`}
                    </span>
                    <span className="cr-assignee__sub">
                      {[person.employee_id, person.email].filter(Boolean).join(" · ") ||
                        "—"}
                    </span>
                  </span>
                  <span className="cr-assignee__title">
                    {person.job_title || person.role || "—"}
                  </span>
                </label>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}

export default EmployeeAssigneePicker;
