/**
 * Compact operational Action Center — resolves into filtered plan list
 */
function CompPlansActionCenter({ summary, loading, onResolve }) {
  const items = summary?.action_center || [];

  return (
    <section className="cp-ops-actions" aria-label="Action required">
      <div className="cp-ops-actions__head">
        <h2 className="cp-ops-actions__title">Action Required</h2>
        {!loading && items.length === 0 ? (
          <span className="cp-ops-actions__clear">No open operational tasks</span>
        ) : null}
      </div>

      {loading && !items.length ? (
        <p className="cp-ops-muted">Checking portfolio readiness…</p>
      ) : items.length === 0 ? null : (
        <ul className="cp-ops-actions__list">
          {items.map((item) => {
            const cta = item.code === "expires_soon" ? "Review" : "Resolve";
            return (
              <li key={item.code} className="cp-ops-actions__item">
                <div className="cp-ops-actions__body">
                  <strong>{item.title}</strong>
                  <span className="cp-ops-actions__count">
                    {item.count ?? 0} Plan{(item.count ?? 0) === 1 ? "" : "s"}
                  </span>
                  <span className="cp-ops-actions__impact">
                    Impact: {item.impact || item.subtitle}
                  </span>
                </div>
                <button
                  type="button"
                  className="cp-ops-actions__btn"
                  onClick={() => onResolve?.(item)}
                >
                  {cta}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default CompPlansActionCenter;
