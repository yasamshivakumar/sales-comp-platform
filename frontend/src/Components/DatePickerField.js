import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { formatDateValue, parseDateValue } from "./dateUtils";

const COMPACT_CLASS = "compact-date-field";

/**
 * Calendar date picker — value/onChange use YYYY-MM-DD strings (API-compatible).
 */
function DatePickerField({
  id,
  label,
  value,
  onChange,
  disabled = false,
  required = false,
  minDate,
  maxDate,
  fullWidth = true,
  size = "small",
  className,
  slotProps,
  ...rest
}) {
  const mergedClass = [COMPACT_CLASS, className, slotProps?.textField?.className]
    .filter(Boolean)
    .join(" ");

  return (
    <DatePicker
      {...rest}
      label={label}
      value={parseDateValue(value)}
      onChange={(next) => onChange?.(next ? formatDateValue(next) : "")}
      disabled={disabled}
      minDate={minDate ? parseDateValue(minDate) : undefined}
      maxDate={maxDate ? parseDateValue(maxDate) : undefined}
      slots={{ openPickerIcon: CalendarMonthOutlinedIcon }}
      slotProps={{
        ...slotProps,
        textField: {
          id,
          size,
          margin: "dense",
          fullWidth,
          required,
          className: mergedClass,
          placeholder: "Select date",
          inputProps: { readOnly: true },
          ...slotProps?.textField,
          className: mergedClass,
        },
        openPickerButton: {
          size: "small",
          ...slotProps?.openPickerButton,
        },
        field: { clearable: true, ...slotProps?.field },
      }}
    />
  );
}

export default DatePickerField;
