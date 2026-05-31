function HierarchySection({ users, form, handleChange, renderField }) {
  const userLabel = (user) => {
    const name = `${user.first_name || ""} ${user.last_name || ""}`.trim();
    return name || user.name || user.email || `User #${user.id}`;
  };

  return (
    <div className="form-grid">
      <p className="section-heading">Reporting hierarchy</p>
      <p className="hierarchy-hint">
        Split percentage is the share the <strong>child (seller)</strong> keeps.
        The parent receives the remainder (e.g. 80 = rep keeps 80%, manager gets 20%).
      </p>

      <div className="form-field">
        <label htmlFor="parent_participant">Parent (manager)</label>
        <select
          id="parent_participant"
          name="parent_participant"
          value={form.parent_participant}
          onChange={handleChange}
        >
          <option value="">Select parent participant</option>
          {users.map((user) => (
            <option key={user.id} value={user.id}>
              {userLabel(user)}
            </option>
          ))}
        </select>
      </div>

      <div className="form-field">
        <label htmlFor="child_participant">Child (direct report)</label>
        <select
          id="child_participant"
          name="child_participant"
          value={form.child_participant}
          onChange={handleChange}
        >
          <option value="">Select child participant</option>
          {users.map((user) => (
            <option key={user.id} value={user.id}>
              {userLabel(user)}
            </option>
          ))}
        </select>
      </div>

      {renderField("split_percentage", "Child retention %", "number")}
    </div>
  );
}

export default HierarchySection;
