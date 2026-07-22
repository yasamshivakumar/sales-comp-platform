import dayjs from "dayjs";

/** Parse API/form date string (YYYY-MM-DD) to dayjs, or null if empty/invalid. */
export function parseDateValue(value) {
  if (!value) return null;
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed : null;
}

/** Format dayjs to YYYY-MM-DD for API/forms. */
export function formatDateValue(value) {
  if (!value || !value.isValid?.()) return "";
  return value.format("YYYY-MM-DD");
}
