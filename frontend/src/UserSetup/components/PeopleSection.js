function PeopleSection({
  renderField,
  renderSelect,
  renderBusinessGroupSelect,
}) {
  return (
    <div className="form-grid">
      <p className="section-heading">People details</p>

      {renderField("username", "Username")}
      {renderField("first_name", "First name")}
      {renderField("last_name", "Last name")}
      {renderField("prefix", "Prefix")}
      {renderField("employee_id", "Employee ID *")}
      {renderSelect("personal_currency", "Currency")}
      {renderBusinessGroupSelect
        ? renderBusinessGroupSelect()
        : renderField("business_group", "Business group")}
      {renderField("region", "Region", "text", "e.g. Maharashtra")}
      {renderField("territory", "Territory", "text", "e.g. West Zone")}
    </div>
  );
}

export default PeopleSection;
