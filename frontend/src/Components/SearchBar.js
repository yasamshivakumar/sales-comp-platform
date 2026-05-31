import React from "react";

function SearchBar({ placeholder, value, onChange, className = "" }) {
  return (
    <div className={`search-bar ${className}`.trim()}>
      <span className="search-bar__icon" aria-hidden="true">
        🔍
      </span>
      <input
        type="text"
        className="search-bar__input"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

export default SearchBar;
