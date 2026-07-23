import { Fragment, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

const ALL_COLUMNS = [
  { key: "employee", label: "Employee", always: true },
  { key: "employee_id", label: "Employee ID" },
  { key: "email", label: "Email" },
  { key: "role", label: "Role" },
  { key: "position", label: "Position" },
  { key: "department", label: "Department" },
  { key: "manager_name", label: "Manager" },
  { key: "business_unit", label: "Business Unit" },
  { key: "region", label: "Region" },
  { key: "territory_name", label: "Territory" },
  { key: "status", label: "Status" },
  { key: "compensation_plan", label: "Compensation Plan" },
  { key: "quota", label: "Quota" },
  { key: "last_login", label: "Last Login" },
  { key: "actions", label: "Actions", always: true, sortable: false },
];

const STORAGE_KEY = "pe-directory-columns-v1";

function loadVisibleColumns() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return ALL_COLUMNS.map((c) => c.key);
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return ALL_COLUMNS.map((c) => c.key);
    const allowed = new Set(ALL_COLUMNS.map((c) => c.key));
    const next = parsed.filter((k) => allowed.has(k));
    ALL_COLUMNS.filter((c) => c.always).forEach((c) => {
      if (!next.includes(c.key)) next.unshift(c.key);
    });
    return next.length ? next : ALL_COLUMNS.map((c) => c.key);
  } catch {
    return ALL_COLUMNS.map((c) => c.key);
  }
}

function StatusBadge({ code, label }) {
  const tone =
    code === "active" || code === "plan_assigned"
      ? "success"
      : code === "pending_activation" || code === "invited"
        ? "warning"
        : code === "suspended" || code === "inactive"
          ? "danger"
          : "neutral";
  return <span className={`pe-badge pe-badge--${tone}`}>{label || code}</span>;
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString();
}

function cellValue(person, key) {
  switch (key) {
    case "employee":
      return person.display_name || person.name || "—";
    case "status":
      return <StatusBadge code={person.status} label={person.status_label} />;
    case "compensation_plan":
      return person.compensation_plan || person.assigned_plan_name || "—";
    case "quota":
      return person.quota_display || person.quota || "—";
    case "last_login":
      return formatDate(person.last_login);
    case "actions":
      return null;
    default:
      return person[key] || "—";
  }
}

export function PeopleColumnPicker({ visible, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="pe-col-picker">
      <button type="button" className="btn-secondary" onClick={() => setOpen((v) => !v)}>
        Columns
      </button>
      {open ? (
        <div className="pe-col-picker__menu" role="menu">
          {ALL_COLUMNS.map((col) => (
            <label key={col.key} className="pe-col-picker__item">
              <input
                type="checkbox"
                disabled={col.always}
                checked={visible.includes(col.key)}
                onChange={() => {
                  if (col.always) return;
                  const next = visible.includes(col.key)
                    ? visible.filter((k) => k !== col.key)
                    : [...visible, col.key];
                  onChange(next);
                  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
                }}
              />
              {col.label}
            </label>
          ))}
          <button type="button" className="cp-btn-ghost" onClick={() => setOpen(false)}>
            Done
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function usePeopleColumns() {
  const [visible, setVisible] = useState(loadVisibleColumns);
  const columns = useMemo(
    () => ALL_COLUMNS.filter((c) => visible.includes(c.key)),
    [visible]
  );
  return { visible, setVisible, columns };
}

function PeopleDataGrid({
  people,
  columns,
  selectedIds,
  onToggleAll,
  onToggleOne,
  ordering,
  onSort,
  expandedId,
  onExpand,
  loading,
  page,
  pageSize,
  total,
  onPageChange,
}) {
  const allSelected = people.length > 0 && people.every((p) => selectedIds.has(p.id));
  const totalPages = Math.max(1, Math.ceil((total || 0) / (pageSize || 50)));

  useEffect(() => {
    if (expandedId && !people.some((p) => p.id === expandedId)) {
      onExpand?.(null);
    }
  }, [people, expandedId, onExpand]);

  const sortIndicator = (key) => {
    if (ordering === key) return " ▲";
    if (ordering === `-${key}`) return " ▼";
    return "";
  };

  return (
    <section className="pe-grid">
      <div className="pe-grid__wrap">
        <table className="pe-table pe-table--enterprise">
          <thead>
            <tr>
              <th className="pe-table__check">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onToggleAll}
                  aria-label="Select all"
                />
              </th>
              <th className="pe-table__expand" aria-label="Expand" />
              {columns.map((col) => (
                <th key={col.key}>
                  {col.sortable === false ? (
                    col.label
                  ) : (
                    <button
                      type="button"
                      className="pe-sort"
                      onClick={() => onSort?.(col.key === "employee" ? "name" : col.key)}
                    >
                      {col.label}
                      {sortIndicator(col.key === "employee" ? "name" : col.key)}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {people.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 2} className="pe-table__empty">
                  {loading ? "Loading participants…" : "No people match this view."}
                </td>
              </tr>
            ) : (
              people.map((person) => {
                const open = expandedId === person.id;
                return (
                  <Fragment key={person.id}>
                    <tr
                      className={`pe-table__row${open ? " is-expanded" : ""}`}
                      onClick={() => onExpand?.(open ? null : person.id)}
                    >
                      <td className="pe-table__check" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(person.id)}
                          onChange={() => onToggleOne(person.id)}
                          aria-label={`Select ${person.display_name}`}
                        />
                      </td>
                      <td className="pe-table__expand">{open ? "▾" : "▸"}</td>
                      {columns.map((col) => {
                        if (col.key === "actions") {
                          return (
                            <td key={col.key} onClick={(e) => e.stopPropagation()}>
                              <Link
                                className="pe-link"
                                to={`/user-setup/${person.id}/overview`}
                              >
                                Open
                              </Link>
                            </td>
                          );
                        }
                        if (col.key === "employee") {
                          return (
                            <td key={col.key}>
                              <strong>{person.display_name || person.name}</strong>
                              <div className="pe-table__sub">{person.email}</div>
                            </td>
                          );
                        }
                        return <td key={col.key}>{cellValue(person, col.key)}</td>;
                      })}
                    </tr>
                    {open ? (
                      <tr className="pe-table__detail">
                        <td colSpan={columns.length + 2}>
                          <div className="pe-expand">
                            <div>
                              <span className="pe-expand__label">Plan</span>
                              <strong>
                                {person.compensation_plan || person.assigned_plan_name || "—"}
                              </strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Quota</span>
                              <strong>{person.quota_display || "—"}</strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Territory</span>
                              <strong>{person.territory_name || "—"}</strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Invite</span>
                              <strong>{person.invitation?.label || "—"}</strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Method</span>
                              <strong>{person.calculation_method || "—"}</strong>
                            </div>
                            <Link
                              className="btn-primary pe-expand__cta"
                              to={`/user-setup/${person.id}/compensation`}
                            >
                              Participant profile
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="pe-pager">
        <span>
          {loading
            ? "Updating…"
            : `${(total || 0).toLocaleString()} participants · page ${page} of ${totalPages}`}
        </span>
        <div className="pe-pager__btns">
          <button
            type="button"
            className="btn-secondary"
            disabled={page <= 1 || loading}
            onClick={() => onPageChange?.(page - 1)}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={page >= totalPages || loading}
            onClick={() => onPageChange?.(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

export default PeopleDataGrid;
export { ALL_COLUMNS, StatusBadge };
