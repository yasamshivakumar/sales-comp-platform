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
        <div>
          <label htmlFor="enable_login">Send invite and enable employee login</label>
          <p className="checkbox-field__hint">
            The employee must open the invite link and set a password before signing in.
          </p>
        </div>
      </div>

      {renderField("name", "Display name *")}
      {renderField("email", "Email *", "email")}
      {renderField(
        "role",
        "Role *",
        "text",
        "e.g. Admin, Finance, Manager, Sales Rep"
      )}
    </div>
  );
}

export default UserSection;
