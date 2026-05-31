function UserSection({ form, handleChange, renderField, renderSelect }) {
  return (
    <div className="form-grid">
      <p className="section-heading">Account & access</p>

      <div className="checkbox-field">
        <input
          type="checkbox"
          id="enable_login"
          name="enable_login"
          checked={form.enable_login}
          onChange={handleChange}
        />
        <label htmlFor="enable_login">Enable login access for this participant</label>
      </div>

      {renderField("name", "Display name *")}
      {renderField("email", "Email *", "email")}
      {renderSelect("role", "Role *", ["Admin", "Manager", "Sales Rep"])}
    </div>
  );
}

export default UserSection;
