function UserSection({ form, handleChange, renderField, renderSelect }) {
  return (
    <div className="form-grid">
      <p className="section-heading">Account & access</p>

      <label
        className={`checkbox-field${form.enable_login ? " checkbox-field--enabled" : ""}`}
        htmlFor="enable_login"
      >
        <input
          type="checkbox"
          id="enable_login"
          name="enable_login"
          checked={form.enable_login}
          onChange={handleChange}
        />
        <span className="checkbox-field__box" aria-hidden="true">
          <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M13.5 4.5 6.5 11.5 3 8"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span className="checkbox-field__copy">
          <span className="checkbox-field__title">
            Send invite and enable employee login
          </span>
          <span className="checkbox-field__hint">
            The employee must open the invite link and set a password before signing in.
          </span>
        </span>
      </label>

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
