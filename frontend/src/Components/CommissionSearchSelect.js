import { useEffect, useId, useMemo, useRef, useState } from "react";
import api from "../api";
import { formatMoney } from "../utils/currency";

function formatOrderDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function commissionLabel(commission) {
  const parts = [
    commission.order_id && `Order ${commission.order_id}`,
    commission.employee_name || commission.employee_id,
    commission.commission_amount != null &&
      formatMoney(commission.commission_amount, commission.currency),
    formatOrderDate(commission.order_date),
  ].filter(Boolean);
  return parts.join(" · ");
}

function CommissionSearchSelect({
  value,
  selectedCommission,
  onSelect,
  disabled,
  placeholder,
}) {
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapperRef = useRef(null);
  const inputId = useId();

  useEffect(() => {
    if (selectedCommission) {
      setQuery(commissionLabel(selectedCommission));
    } else if (!value) {
      setQuery("");
    }
  }, [selectedCommission, value]);

  useEffect(() => {
    let cancelled = false;
    const term = query.trim();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setLoadError("");
      const params = new URLSearchParams();
      if (term) {
        params.set("q", term);
      } else {
        params.set("limit", "15");
      }
      api
        .get(`commissions/?${params.toString()}`)
        .then((res) => {
          if (cancelled) return;
          const data = res.data;
          const rows = Array.isArray(data) ? data : data?.results || [];
          setCommissions(rows);
        })
        .catch(() => {
          if (!cancelled) {
            setCommissions([]);
            setLoadError("Could not load commissions.");
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, term ? 250 : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    const handleClick = (event) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = useMemo(() => commissions, [commissions]);

  const applySelection = (commission) => {
    setQuery(commissionLabel(commission));
    setOpen(false);
    onSelect?.(commission);
  };

  const handleInputChange = (event) => {
    const next = event.target.value;
    setQuery(next);
    setOpen(true);
    if (!next.trim()) {
      onSelect?.(null);
    }
  };

  const handleFocus = () => {
    setOpen(true);
    if (selectedCommission && query === commissionLabel(selectedCommission)) {
      setQuery("");
      onSelect?.(null);
    }
  };

  const showBrowseHint = !query.trim() && commissions.length >= 15;

  return (
    <div className="commission-search" ref={wrapperRef}>
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        className="commission-search__input input"
        value={query}
        onChange={handleInputChange}
        onFocus={handleFocus}
        disabled={disabled}
        placeholder={placeholder || "Search by order ID, employee, or amount…"}
        autoComplete="off"
      />
      {showBrowseHint && (
        <p className="commission-search__hint">Showing recent commissions. Type to search.</p>
      )}
      {open && (
        <ul className="commission-search__list" role="listbox" aria-labelledby={inputId}>
          {loading && filtered.length === 0 && (
            <li className="commission-search__empty">Loading commissions…</li>
          )}
          {!loadError && filtered.length === 0 && !loading && (
            <li className="commission-search__empty">No commissions found</li>
          )}
          {loadError && (
            <li className="commission-search__empty commission-search__empty--error">{loadError}</li>
          )}
          {filtered.map((commission) => {
            const blocked = commission.has_open_dispute;
            return (
              <li key={commission.id} role="option" aria-disabled={blocked}>
                <button
                  type="button"
                  className={`commission-search__option${blocked ? " commission-search__option--disabled" : ""}`}
                  disabled={blocked}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => !blocked && applySelection(commission)}
                >
                  <span className="commission-search__primary">
                    {commission.order_id || `Commission #${commission.id}`}
                  </span>
                  <span className="commission-search__secondary">
                    {commission.employee_name || commission.employee_id || "—"}
                    {commission.commission_amount != null &&
                      ` · ${formatMoney(commission.commission_amount, commission.currency)}`}
                    {commission.order_date && ` · ${formatOrderDate(commission.order_date)}`}
                  </span>
                  {blocked && (
                    <span className="commission-search__badge">Dispute already open</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default CommissionSearchSelect;
