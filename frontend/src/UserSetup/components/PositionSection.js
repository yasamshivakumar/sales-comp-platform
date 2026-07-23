function PositionSection({ renderField }) {
  return (
    <div className="form-grid">
      <p className="section-heading">Position assignment</p>
      <p className="hierarchy-hint">
        Optional job position used for org reporting and plan matching later.
      </p>

      {renderField("position_name", "Position name")}
      {renderField("position_title", "Position title")}
    </div>
  );
}

export default PositionSection;
