import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { formatMonthValue, parseMonthValue } from "./dateUtils";

const COMPACT_CLASS = "compact-date-field";

/**
 * Month/year picker — value/onChange use YYYY-MM strings.
 */
function MonthPickerField({
  id,
  label,
  value,
  onChange,
  disabled = false,
  required = false,
  fullWidth = true,
  size = "small",
  className,
  helperText,
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
      views={["year", "month"]}
      openTo="month"
      value={parseMonthValue(value)}
      onChange={(next) => onChange?.(next ? formatMonthValue(next) : "")}
      disabled={disabled}
      slots={{ openPickerIcon: CalendarMonthOutlinedIcon }}
      slotProps={{
        ...slotProps,
        textField: {
          id,
          size,
          margin: "dense",
          fullWidth,
          required,
          placeholder: "Select month",
          helperText,
          inputProps: { readOnly: true },
          FormHelperTextProps: { sx: { mt: 0.25, fontSize: "0.7rem" } },
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

export default MonthPickerField;
