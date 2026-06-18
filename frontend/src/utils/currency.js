export const CURRENCY_OPTIONS = [
  { value: "INR", label: "INR — Indian Rupee" },
  { value: "USD", label: "USD — US Dollar" },
  { value: "EUR", label: "EUR — Euro" },
  { value: "AUD", label: "AUD — Australian Dollar" },
];

const CURRENCY_META = {
  INR: { locale: "en-IN", symbol: "₹" },
  USD: { locale: "en-US", symbol: "$" },
  EUR: { locale: "de-DE", symbol: "€" },
  AUD: { locale: "en-AU", symbol: "A$" },
};

export function normalizeCurrency(code, fallback = "INR") {
  const normalized = String(code || "")
    .trim()
    .toUpperCase();
  return CURRENCY_META[normalized] ? normalized : fallback;
}

export function formatMoney(value, currencyCode = "INR", { compact = false } = {}) {
  const code = normalizeCurrency(currencyCode);
  const meta = CURRENCY_META[code];
  const amount = parseFloat(value) || 0;
  const fractionDigits = compact ? 0 : 2;
  return `${meta.symbol}${amount.toLocaleString(meta.locale, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}`;
}

export function activeCurrencyTotals(totalsByCurrency, valueKey = "total") {
  return (totalsByCurrency || [])
    .map((row) => ({
      ...row,
      currency: normalizeCurrency(row.currency),
      [valueKey]: parseFloat(row[valueKey]) || 0,
    }))
    .filter((row) => row[valueKey] > 0)
    .sort((a, b) => a.currency.localeCompare(b.currency));
}

export function formatMoneyList(totalsByCurrency, valueKey = "total", { compact = false } = {}) {
  const rows = activeCurrencyTotals(totalsByCurrency, valueKey);
  if (!rows.length) return null;
  if (rows.length === 1) {
    return formatMoney(rows[0][valueKey], rows[0].currency, { compact });
  }
  return rows
    .map((row) => formatMoney(row[valueKey], row.currency, { compact }))
    .join(" · ");
}

export function formatDashboardAmount(
  totalsByCurrency,
  fallbackTotal,
  fallbackCurrency = "INR",
  { compact = false } = {}
) {
  const formatted = formatMoneyList(totalsByCurrency, "total", { compact });
  if (formatted) return formatted;
  return formatMoney(fallbackTotal, fallbackCurrency, { compact });
}

export function primaryCurrencyFromPayload(payload, fallback = "INR") {
  const active = activeCurrencyTotals(payload?.totals_by_currency);
  if (active.length === 1) return active[0].currency;
  return normalizeCurrency(payload?.primary_currency || payload?.personal_currency, fallback);
}
