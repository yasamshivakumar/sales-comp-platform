function MarketingButton({
  variant = "primary",
  type = "button",
  href,
  onClick,
  children,
  className = "",
}) {
  const classes = `mkt-btn mkt-btn--${variant}${className ? ` ${className}` : ""}`;

  if (href) {
    return (
      <a className={classes} href={href}>
        {children}
      </a>
    );
  }

  return (
    <button type={type} className={classes} onClick={onClick}>
      {children}
    </button>
  );
}

export default MarketingButton;
