function TitleSection({ renderField, renderSelect }) {
  return (
    <div className="form-grid">
      <p className="section-heading">Title & pay period</p>

      {renderField("title", "Job title")}
      {renderSelect("pay_period_type", "Pay period", ["Monthly", "Quarterly", "Annual"])}
    </div>
  );
}

export default TitleSection;
