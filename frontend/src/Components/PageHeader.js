function PageHeader({ title, subtitle, badge, children }) {
  return (
    <header className="page-header animate-in">
      <div className="page-header__text">
        {badge && <span className="page-header__badge">{badge}</span>}
        <h1 className="page-header__title">{title}</h1>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
      </div>
      {children && <div className="page-header__actions">{children}</div>}
    </header>
  );
}

export default PageHeader;
