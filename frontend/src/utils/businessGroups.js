import { normalizeCurrency } from "./currency";

export const BUSINESS_GROUP_OPTIONS = [
  { value: "India", label: "India", currency: "INR" },
  { value: "USA", label: "USA", currency: "USD" },
  { value: "Australia", label: "Australia", currency: "AUD" },
  { value: "Europe", label: "Europe", currency: "EUR" },
];

const ALIASES = {
  india: "India",
  usa: "USA",
  us: "USA",
  "united states": "USA",
  america: "USA",
  australia: "Australia",
  au: "Australia",
  europe: "Europe",
  eu: "Europe",
};

const BY_VALUE = Object.fromEntries(
  BUSINESS_GROUP_OPTIONS.map((item) => [item.value, item])
);

export function normalizeBusinessGroup(value, fallback = "India") {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  if (BY_VALUE[raw]) return raw;
  const alias = ALIASES[raw.toLowerCase()];
  if (alias) return alias;
  const match = BUSINESS_GROUP_OPTIONS.find(
    (item) => item.value.toLowerCase() === raw.toLowerCase()
  );
  return match?.value || raw;
}

export function currencyForBusinessGroup(businessGroup, personalCurrency) {
  const normalized = normalizeBusinessGroup(businessGroup, "");
  const item = BY_VALUE[normalized];
  if (item) return item.currency;
  return normalizeCurrency(personalCurrency, "");
}

export function businessGroupLabel(value) {
  const normalized = normalizeBusinessGroup(value, "");
  return BY_VALUE[normalized]?.label || normalized || "—";
}
