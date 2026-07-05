import { useEffect, useId, useRef, useState } from "react";
import api from "../api";

function EmployeeSearchSelect({ value, onSelect, disabled, placeholder }) {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value || "");
  const wrapperRef = useRef(null);
  const inputId = useId();

  useEffect(() => {
    setQuery(value || "");
  }, [value]);

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
        .get(`employees/directory/?${params.toString()}`)
        .then((res) => {
          if (!cancelled) setEmployees(res.data || []);
        })
        .catch(() => {
          if (!cancelled) {
            setEmployees([]);
            setLoadError("Could not load employees. Refresh the page or restart the API server.");
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

  const applySelection = (employee) => {
    setQuery(employee.employee_id);
    setOpen(false);
    onSelect?.(employee);
  };

  const handleInputChange = (event) => {
    const next = event.target.value;
    setQuery(next);
    setOpen(true);
    if (!next.trim()) {
      onSelect?.(null);
    }
  };

  const handleBlur = () => {
    window.setTimeout(() => setOpen(false), 150);
    const trimmed = query.trim();
    if (!trimmed) {
      onSelect?.(null);
      return;
    }
    const match = employees.find(
      (employee) => employee.employee_id.toLowerCase() === trimmed.toLowerCase()
    );
    if (match) {
      applySelection(match);
      return;
    }
    onSelect?.({
      employee_id: trimmed,
      display_name: "",
      position_name: "",
      manager_name: "",
      territory_id: null,
      territory_name: "",
    });
  };

  const showBrowseHint = !query.trim() && employees.length >= 15;
  const listboxId = `${inputId}-listbox`;

  return (
    <div className="employee-search" ref={wrapperRef}>
      <input
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        className="employee-search__input"
        value={query}
        onChange={handleInputChange}
        onFocus={() => setOpen(true)}
        onBlur={handleBlur}
        disabled={disabled}
        placeholder={placeholder || "Search employee ID or name…"}
        autoComplete="off"
      />
      {showBrowseHint && (
        <p className="employee-search__hint">Showing 15 employees. Type to search all.</p>
      )}
      {open && (
        <ul
          id={listboxId}
          className="employee-search__list"
          role="listbox"
          aria-labelledby={inputId}
        >
          {loading && employees.length === 0 && (
            <li className="employee-search__empty">Loading employees…</li>
          )}
          {!loadError && employees.length === 0 && !loading && (
            <li className="employee-search__empty">No employees found in User Setup</li>
          )}
          {loadError && (
            <li className="employee-search__empty employee-search__empty--error">{loadError}</li>
          )}
          {employees.map((employee) => (
              <li
                key={employee.id}
                role="option"
                aria-selected={String(value) === String(employee.employee_id)}
              >
                <button
                  type="button"
                  className="employee-search__option"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => applySelection(employee)}
                >
                  <span className="employee-search__id">{employee.employee_id}</span>
                  <span className="employee-search__name">{employee.display_name}</span>
                  {employee.position_name && (
                    <span className="employee-search__meta">{employee.position_name}</span>
                  )}
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

export default EmployeeSearchSelect;
