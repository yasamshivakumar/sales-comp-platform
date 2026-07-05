function BrowserFrame({ title = "Incentra workspace", children }) {
  return (
    <div className="mkt-browser" aria-hidden={!children}>
      <div className="mkt-browser__chrome">
        <span />
        <span />
        <span />
        <span className="mkt-browser__title">{title}</span>
      </div>
      <div className="mkt-browser__viewport">{children}</div>
    </div>
  );
}

export default BrowserFrame;
