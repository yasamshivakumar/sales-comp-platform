const ICON_PATHS = {
  plans: (
  <>
    <rect x="3" y="4" width="18" height="4" rx="1" fill="currentColor" opacity="0.35" />
    <rect x="3" y="10" width="14" height="3" rx="1" fill="currentColor" opacity="0.55" />
    <rect x="3" y="15" width="18" height="3" rx="1" fill="currentColor" />
  </>
  ),
  participants: (
  <>
    <circle cx="9" cy="8" r="3" fill="currentColor" />
    <path d="M3 19c0-3.3 2.7-5 6-5s6 1.7 6 5" fill="currentColor" opacity="0.55" />
    <circle cx="17" cy="9" r="2.5" fill="currentColor" opacity="0.45" />
  </>
  ),
  "crm-sync": (
  <>
    <path d="M7 12h10M12 7v10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <circle cx="5" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
    <circle cx="19" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="2" />
  </>
  ),
  commissions: (
  <>
    <path d="M4 17V7l8-4 8 4v10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <path d="M9 17v-5h6v5" fill="currentColor" opacity="0.55" />
  </>
  ),
  dashboard: (
  <>
    <rect x="4" y="12" width="4" height="8" rx="1" fill="currentColor" opacity="0.45" />
    <rect x="10" y="8" width="4" height="12" rx="1" fill="currentColor" opacity="0.7" />
    <rect x="16" y="5" width="4" height="15" rx="1" fill="currentColor" />
  </>
  ),
  check: (
    <path d="M5 12l4 4 10-10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
};

export function MarketingIcon({ name, className = "" }) {
  return (
    <svg
      className={className}
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      {ICON_PATHS[name]}
    </svg>
  );
}
