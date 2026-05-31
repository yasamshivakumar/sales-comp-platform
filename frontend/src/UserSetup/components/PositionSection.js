function PositionSection({ renderField }) {
  return (
    <div className="form-grid">
      <p className="section-heading">Position assignment</p>
      <p className="hierarchy-hint">
        Position name is used to match compensation plans during order processing.
      </p>

      {renderField("position_name", "Position name")}
      {renderField("position_title", "Position title")}
    </div>
  );
}

export default PositionSection;
