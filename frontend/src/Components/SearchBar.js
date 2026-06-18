import SearchIcon from "@mui/icons-material/Search";

function SearchBar({ placeholder, value, onChange, onKeyDown, className = "" }) {
  return (
    <div className={`search-bar ${className}`.trim()}>
      <SearchIcon className="search-bar__icon" aria-hidden="true" />
      <input
        type="search"
        className="search-bar__input"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        aria-label={placeholder || "Search"}
      />
    </div>
  );
}

export default SearchBar;
