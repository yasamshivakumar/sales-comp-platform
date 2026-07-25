import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import Fade from "@mui/material/Fade";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { formatDateValue, parseDateValue } from "./dateUtils";
import { useTheme } from "../ThemeContext";

const COMPACT_CLASS = "compact-date-field";

/** Above theme.zIndex.modal (2200) and custom overlays (~1200–1500). */
export const DATE_PICKER_Z_INDEX = 2300;

/** Always use the desktop popper anchored below the field (never a centered dialog). */
const DESKTOP_POPPER_MEDIA_QUERY = "(min-width: 0px)";

/** Instant exit — Grow's scale-down reads as "minimize then close". */
function InstantFade(props) {
  return <Fade {...props} timeout={0} />;
}

const DEFAULT_POPPER_MODIFIERS = [
  {
    name: "flip",
    enabled: true,
    options: {
      fallbackPlacements: ["top-start", "bottom-end", "top-end", "top", "bottom"],
      padding: 8,
    },
  },
  {
    name: "preventOverflow",
    enabled: true,
    options: {
      altAxis: true,
      tether: false,
      rootBoundary: "viewport",
      padding: 8,
    },
  },
  {
    name: "offset",
    options: { offset: [0, 6] },
  },
];

function getPortalContainer() {
  if (typeof document === "undefined") return undefined;
  return document.body;
}

/**
 * Shared calendar date picker for the whole app.
 * Visual theme: styles/date-picker.css + theme/datePickerTokens.js
 * value / onChange use YYYY-MM-DD strings (API-compatible).
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
  hideLabel = false,
  slots,
  ...rest
}) {
  const { isDarkMode } = useTheme();
  const themeSuffix = isDarkMode ? "dark" : "light";
  const mergedClass = [
    COMPACT_CLASS,
    `compact-date-field--${themeSuffix}`,
    className,
    slotProps?.textField?.className,
  ]
    .filter(Boolean)
    .join(" ");

  const callerPopper = slotProps?.popper || {};
  const callerModifiers = Array.isArray(callerPopper.modifiers)
    ? callerPopper.modifiers
    : [];

  const paperClass = `app-date-picker-paper app-date-picker-paper--${themeSuffix}`;

  return (
    <DatePicker
      {...rest}
      label={hideLabel ? undefined : label}
      value={parseDateValue(value)}
      onChange={(next) => onChange?.(next ? formatDateValue(next) : "")}
      disabled={disabled}
      minDate={minDate ? parseDateValue(minDate) : undefined}
      maxDate={maxDate ? parseDateValue(maxDate) : undefined}
      desktopModeMediaQuery={DESKTOP_POPPER_MEDIA_QUERY}
      closeOnSelect
      reduceAnimations
      slots={{
        openPickerIcon: CalendarMonthOutlinedIcon,
        ...slots,
        desktopTransition: InstantFade,
      }}
      slotProps={{
        ...slotProps,
        textField: {
          id,
          size,
          margin: "dense",
          fullWidth,
          required,
          placeholder: "Select date",
          ...slotProps?.textField,
          className: mergedClass,
          inputProps: {
            "aria-label": hideLabel && label ? label : undefined,
            ...slotProps?.textField?.inputProps,
          },
        },
        openPickerButton: {
          size: "small",
          "aria-label": label ? `Open ${label} calendar` : "Open calendar",
          ...slotProps?.openPickerButton,
        },
        field: { clearable: true, ...slotProps?.field },
        desktopTransition: {
          timeout: 0,
          ...slotProps?.desktopTransition,
        },
        popper: {
          disablePortal: false,
          container: getPortalContainer,
          placement: "bottom-start",
          ...callerPopper,
          className: [
            "app-date-picker-popper",
            `app-date-picker-popper--${themeSuffix}`,
            callerPopper.className,
          ]
            .filter(Boolean)
            .join(" "),
          modifiers: [...DEFAULT_POPPER_MODIFIERS, ...callerModifiers],
          style: {
            zIndex: DATE_PICKER_Z_INDEX,
            ...(callerPopper.style || {}),
          },
          sx: {
            zIndex: `${DATE_PICKER_Z_INDEX} !important`,
            ...(callerPopper.sx || {}),
          },
        },
        mobilePaper: {
          className: `${paperClass} app-date-picker-paper--mobile`,
          elevation: 0,
          ...slotProps?.mobilePaper,
        },
        desktopPaper: {
          className: paperClass,
          elevation: 0,
          ...slotProps?.desktopPaper,
        },
        actionBar: {
          ...slotProps?.actionBar,
          actions: [],
        },
      }}
    />
  );
}

export default DatePickerField;
