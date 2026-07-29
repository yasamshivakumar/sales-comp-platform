import { RoleChip, SoftChip, StatusChip, EmployeeAvatar, EmptyValue } from "./peopleCells";

/**
 * Mobile / compact card representation of a participant row.
 */
export default function EmployeeSummaryCard({
  person,
  selected,
  onToggle,
  onPreview,
  onOpenProfile,
}) {
  const name = person.display_name || person.name || "Unnamed";
  return (
    <article className={`pe-mobile-card${selected ? " is-selected" : ""}`}>
      <header className="pe-mobile-card__head">
        <label className="pe-mobile-card__check">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle?.(person.id)}
            aria-label={`Select ${name}`}
          />
        </label>
        <button type="button" className="pe-identity" onClick={() => onPreview?.(person)}>
          <EmployeeAvatar person={person} size={44} />
          <span className="pe-identity__text">
            <span className="pe-identity__name">{name}</span>
            <span className="pe-identity__id">{person.employee_id || "No employee ID"}</span>
            <span className="pe-identity__email">{person.email || "No email"}</span>
          </span>
        </button>
      </header>
      <div className="pe-mobile-card__meta">
        <StatusChip code={person.status} label={person.status_label} />
        <RoleChip role={person.role} />
        <SoftChip
          value={person.compensation_plan || person.assigned_plan_name}
          empty="No plan"
        />
      </div>
      <dl className="pe-mobile-card__dl">
        <div>
          <dt>Manager</dt>
          <dd>{person.manager_name || <EmptyValue label="No manager" />}</dd>
        </div>
        <div>
          <dt>Territory</dt>
          <dd>{person.territory_name || <EmptyValue label="No territory" />}</dd>
        </div>
        <div>
          <dt>Quota</dt>
          <dd>
            {person.quota_display || person.quota || <EmptyValue label="No quota" />}
          </dd>
        </div>
      </dl>
      <footer className="pe-mobile-card__foot">
        <button type="button" className="btn-secondary" onClick={() => onPreview?.(person)}>
          Preview
        </button>
        <button type="button" className="btn-primary" onClick={() => onOpenProfile?.(person)}>
          Open profile
        </button>
      </footer>
    </article>
  );
}
