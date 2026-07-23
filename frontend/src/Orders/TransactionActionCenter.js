function TransactionActionCenter({ summary, loading, onResolve }) {
  const items = summary?.action_center || [];

  return (
    <section className="tx-actions" aria-label="Action required">
      <div className="tx-actions__head">
        <h2>Action Required</h2>
        {!loading && !items.length ? (
          <span className="tx-actions__clear">No open operational alerts</span>
        ) : null}
      </div>
      {loading && !items.length ? (
        <p className="tx-muted">Checking order readiness…</p>
      ) : items.length === 0 ? null : (
        <ul className="tx-actions__list">
          {items.map((item) => (
            <li key={item.code} className="tx-actions__item">
              <div>
                <strong>{item.title}</strong>
                <p>{item.subtitle}</p>
                <span>Impact: {item.impact}</span>
              </div>
              <button type="button" className="tx-actions__btn" onClick={() => onResolve?.(item)}>
                {item.cta || "Review"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default TransactionActionCenter;
