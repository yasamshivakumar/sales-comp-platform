function PeopleSection({
  renderField,
  renderSelect,
  renderBusinessGroupSelect,
  renderTerritorySelect,
  newTerritoryName,
  newTerritoryCode,
  onNewTerritoryNameChange,
  onNewTerritoryCodeChange,
  onCreateTerritory,
  creatingTerritory,
}) {
  return (
    <div className="form-grid">
      <p className="section-heading">People details</p>

      {renderField("username", "Username")}
      {renderField("first_name", "First name")}
      {renderField("last_name", "Last name")}
      {renderField("prefix", "Prefix")}
      {renderField("employee_id", "Employee ID *")}
      {renderField("personal_target", "Personal target", "number")}
      {renderSelect("personal_currency", "Currency")}
      {renderBusinessGroupSelect
        ? renderBusinessGroupSelect()
        : renderField("business_group", "Business group")}
      {renderField("region", "Region", "text", "e.g. Maharashtra")}
      {renderTerritorySelect && renderTerritorySelect()}

      <div className="form-field" style={{ gridColumn: "1 / -1" }}>
        <p className="section-heading" style={{ marginTop: 8, marginBottom: 8 }}>
          Add territory
        </p>
        <p style={{ margin: "0 0 10px", fontSize: "0.85rem", color: "var(--text-muted, #64748b)" }}>
          Create a territory here, then select it above when saving the participant.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: "1 1 160px" }}>
            <span>Territory name</span>
            <input
              className="input"
              value={newTerritoryName || ""}
              onChange={onNewTerritoryNameChange}
              placeholder="e.g. West Zone"
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: "1 1 120px" }}>
            <span>Code</span>
            <input
              className="input"
              value={newTerritoryCode || ""}
              onChange={onNewTerritoryCodeChange}
              placeholder="e.g. WEST"
            />
          </label>
          <button
            type="button"
            className="btn-secondary"
            onClick={onCreateTerritory}
            disabled={creatingTerritory}
          >
            {creatingTerritory ? "Adding…" : "Add territory"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PeopleSection;
