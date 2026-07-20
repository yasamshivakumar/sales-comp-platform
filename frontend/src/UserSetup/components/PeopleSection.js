function PeopleSection({
  renderField,
  renderSelect,
  renderBusinessGroupSelect,
  renderTerritorySelect,
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
    </div>
  );
}

export default PeopleSection;
