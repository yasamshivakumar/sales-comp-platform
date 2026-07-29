import { Fragment, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Tooltip,
} from "@mui/material";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import PaymentsOutlinedIcon from "@mui/icons-material/PaymentsOutlined";
import ShoppingBagOutlinedIcon from "@mui/icons-material/ShoppingBagOutlined";
import BlockOutlinedIcon from "@mui/icons-material/BlockOutlined";
import {
  CompensationPlanChip,
  EmployeeIdentityCell,
  EmptyValue,
  RelativeTime,
  RoleChip,
  SoftChip,
  StatusChip,
} from "./enterprise/peopleCells";
import EmployeeSummaryCard from "./enterprise/EmployeeSummaryCard";

const ALL_COLUMNS = [
  { key: "employee", label: "Employee", always: true },
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

const STORAGE_KEY = "pe-directory-columns-v2";

function loadVisibleColumns() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [
        "employee",
        "role",
        "manager_name",
        "status",
        "compensation_plan",
        "quota",
        "territory_name",
        "last_login",
        "actions",
      ];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return ALL_COLUMNS.map((c) => c.key);
    const allowed = new Set(ALL_COLUMNS.map((c) => c.key));
    const next = parsed.filter((k) => allowed.has(k));
    ALL_COLUMNS.filter((c) => c.always).forEach((c) => {
      if (!next.includes(c.key)) next.push(c.key);
    });
    return next.length ? next : ALL_COLUMNS.map((c) => c.key);
  } catch {
    return ALL_COLUMNS.map((c) => c.key);
  }
}

function RowActionsMenu({ person, onPreview, onDeactivate }) {
  const [anchor, setAnchor] = useState(null);
  const navigate = useNavigate();
  const open = Boolean(anchor);
  const close = () => setAnchor(null);
  const go = (path) => {
    close();
    navigate(path);
  };

  return (
    <>
      <Tooltip title="Preview">
        <IconButton
          size="small"
          aria-label={`Preview ${person.display_name || person.name}`}
          onClick={(e) => {
            e.stopPropagation();
            onPreview?.(person);
          }}
        >
          <VisibilityOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="More actions">
        <IconButton
          size="small"
          aria-label="More actions"
          aria-haspopup="menu"
          onClick={(e) => {
            e.stopPropagation();
            setAnchor(e.currentTarget);
          }}
        >
          <MoreVertIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchor}
        open={open}
        onClose={close}
        onClick={(e) => e.stopPropagation()}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <MenuItem onClick={() => go(`/user-setup/${person.id}/overview`)}>
          <ListItemIcon>
            <PersonOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>View profile</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => go(`/user-setup/${person.id}/organization`)}>
          <ListItemIcon>
            <EditOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit employee</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => go(`/user-setup/${person.id}/compensation`)}>
          <ListItemIcon>
            <AccountTreeOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Assign compensation plan</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => go(`/user-setup/${person.id}/organization`)}>
          <ListItemIcon>
            <EditOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Assign manager</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => go(`/user-setup/${person.id}/commissions`)}>
          <ListItemIcon>
            <PaymentsOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>View commission history</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => go(`/user-setup/${person.id}/transactions`)}>
          <ListItemIcon>
            <ShoppingBagOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>View orders</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            close();
            onDeactivate?.(person);
          }}
        >
          <ListItemIcon>
            <BlockOutlinedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Deactivate</ListItemText>
        </MenuItem>
      </Menu>
    </>
  );
}

function renderCell(person, key, { onPreview }) {
  switch (key) {
    case "employee":
      return (
        <EmployeeIdentityCell
          person={person}
          onOpen={() => onPreview?.(person)}
        />
      );
    case "role":
      return <RoleChip role={person.role} />;
    case "position":
      return <SoftChip value={person.position || person.position_title} empty="No position" />;
    case "department":
      return person.department ? (
        <span className="pe-muted-text">{person.department}</span>
      ) : (
        <EmptyValue label="No department" />
      );
    case "manager_name":
      return person.manager_name ? (
        <span className="pe-linkish">{person.manager_name}</span>
      ) : (
        <EmptyValue label="No manager" />
      );
    case "business_unit":
      return (
        <SoftChip
          value={person.business_unit || person.business_group}
          empty="No business unit"
        />
      );
    case "region":
      return <SoftChip value={person.region} empty="No region" />;
    case "territory_name":
      return person.territory_name ? (
        <span className="pe-tag">{person.territory_name}</span>
      ) : (
        <EmptyValue label="No territory" />
      );
    case "status":
      return <StatusChip code={person.status} label={person.status_label} />;
    case "compensation_plan":
      return (
        <CompensationPlanChip
          plan={person.compensation_plan || person.assigned_plan_name}
        />
      );
    case "quota":
      return person.quota_display || person.quota ? (
        <strong className="pe-quota">{person.quota_display || person.quota}</strong>
      ) : (
        <EmptyValue label="No quota" />
      );
    case "last_login":
      return <RelativeTime value={person.last_login} />;
    default:
      return person[key] || <EmptyValue />;
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
  onPreview,
  onDeactivate,
}) {
  const navigate = useNavigate();
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

  const cell = (person, key) => renderCell(person, key, { onPreview });
  const showSkeleton = loading && people.length === 0;

  return (
    <section className="pe-grid pe-grid--enterprise">
      <div className="pe-grid__wrap">
        <table className="pe-table pe-table--enterprise pe-table--rich">
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
                <th
                  key={col.key}
                  className={col.key === "actions" ? "pe-table__actions-col" : undefined}
                >
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
            {showSkeleton
              ? Array.from({ length: 6 }).map((_, idx) => (
                  <tr key={`skel-${idx}`} className="pe-skel-row" aria-hidden>
                    <td colSpan={columns.length + 2}>
                      <span className="pe-skel-bar" style={{ width: `${70 - idx * 6}%` }} />
                    </td>
                  </tr>
                ))
              : null}
            {!showSkeleton && people.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 2} className="pe-table__empty">
                  No people match this view.
                </td>
              </tr>
            ) : null}
            {!showSkeleton
              ? people.map((person) => {
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
                          aria-label={`Select ${person.display_name || person.name}`}
                        />
                      </td>
                      <td className="pe-table__expand">{open ? "▾" : "▸"}</td>
                      {columns.map((col) => {
                        if (col.key === "actions") {
                          return (
                            <td
                              key={col.key}
                              className="pe-table__actions-col"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <div className="pe-row-actions">
                                <RowActionsMenu
                                  person={person}
                                  onPreview={onPreview}
                                  onDeactivate={onDeactivate}
                                />
                              </div>
                            </td>
                          );
                        }
                        return (
                          <td key={col.key} className={col.key === "employee" ? "pe-td-employee" : undefined}>
                            {cell(person, col.key)}
                          </td>
                        );
                      })}
                    </tr>
                    {open ? (
                      <tr className="pe-table__detail">
                        <td colSpan={columns.length + 2}>
                          <div className="pe-expand pe-expand--rich">
                            <div>
                              <span className="pe-expand__label">Manager</span>
                              <strong>{person.manager_name || "No manager"}</strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Department</span>
                              <strong>{person.department || "No department"}</strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Business unit</span>
                              <strong>
                                {person.business_unit || person.business_group || "Not assigned"}
                              </strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Quota</span>
                              <strong>{person.quota_display || "No quota"}</strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Compensation plan</span>
                              <strong>
                                {person.compensation_plan ||
                                  person.assigned_plan_name ||
                                  "Not assigned"}
                              </strong>
                            </div>
                            <div>
                              <span className="pe-expand__label">Territory</span>
                              <strong>{person.territory_name || "No territory"}</strong>
                            </div>
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={(e) => {
                                e.stopPropagation();
                                onPreview?.(person);
                              }}
                            >
                              Quick preview
                            </button>
                            <Link
                              className="btn-primary pe-expand__cta"
                              to={`/user-setup/${person.id}/compensation`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              Full profile
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })
              : null}
          </tbody>
        </table>
      </div>

      <div className="pe-mobile-cards" aria-label="Participants">
        {people.map((person) => (
          <EmployeeSummaryCard
            key={person.id}
            person={person}
            selected={selectedIds.has(person.id)}
            onToggle={onToggleOne}
            onPreview={onPreview}
            onOpenProfile={(p) => navigate(`/user-setup/${p.id}/overview`)}
          />
        ))}
        {!loading && people.length === 0 ? (
          <p className="pe-table__empty">No people match this view.</p>
        ) : null}
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
export { ALL_COLUMNS, StatusChip as StatusBadge };
