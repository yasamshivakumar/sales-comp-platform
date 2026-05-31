function PeopleSection({ renderField }) {
  return (
    <div className="form-grid">
      <p className="section-heading">People details</p>

      {renderField("username", "Username")}
      {renderField("first_name", "First name")}
      {renderField("last_name", "Last name")}
      {renderField("prefix", "Prefix")}
      {renderField("employee_id", "Employee ID *")}
      {renderField("personal_target", "Personal target", "number")}
      {renderField("personal_currency", "Currency")}
      {renderField("business_group", "Business group")}
    </div>
  );
}

export default PeopleSection;
