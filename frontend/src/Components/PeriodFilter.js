import DatePickerField from "./DatePickerField";

function PeriodFilter({
  startDate,
  endDate,
  onStartChange,
  onEndChange,
  onSubmit,
  submitLabel = "Apply",
  loading = false,
  children,
}) {
  return (
    <div className="enterprise-form-row">
      <DatePickerField
        label="From"
        value={startDate}
        onChange={onStartChange}
        maxDate={endDate || undefined}
        fullWidth={false}
        slotProps={{ textField: { className: "input" } }}
      />
      <DatePickerField
        label="To"
        value={endDate}
        onChange={onEndChange}
        minDate={startDate || undefined}
        fullWidth={false}
        slotProps={{ textField: { className: "input" } }}
      />
      {onSubmit && (
        <button type="button" className="btn-primary" onClick={onSubmit} disabled={loading}>
          {loading ? "Loading…" : submitLabel}
        </button>
      )}
      {children}
    </div>
  );
}

export default PeriodFilter;
