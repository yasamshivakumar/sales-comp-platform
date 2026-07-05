import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PRODUCT_AREAS, SOLUTIONS_BY_FUNCTION, getProductArea, getTeamSolution } from "./marketingData";
import { MarketingNavContext } from "./marketingNavContext";
import MarketingHome from "./pages/MarketingHome";
import MarketingProductsIndex from "./pages/MarketingProductsIndex";
import MarketingProductPage from "./pages/MarketingProductPage";
import MarketingTeamsIndex from "./pages/MarketingTeamsIndex";
import MarketingTeamPage from "./pages/MarketingTeamPage";
import MarketingDemo from "./pages/MarketingDemo";
import "./marketing.css";
import "./marketing-enterprise.css";
import "./marketing-premium.css";

function MarketingLayout() {
  const [view, setView] = useState({ type: "home" });
  const [openMenu, setOpenMenu] = useState(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [navScrolled, setNavScrolled] = useState(false);

  const navigate = useCallback((nextView) => {
    setView(nextView);
    setOpenMenu(null);
    setMobileNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const toggleMenu = (menu, event) => {
    event?.stopPropagation();
    setOpenMenu((current) => (current === menu ? null : menu));
  };

  const handleMenuAction = (action) => (event) => {
    event.stopPropagation();
    action();
  };

  const closeMenus = useCallback(() => {
    setOpenMenu(null);
    setMobileNavOpen(false);
  }, []);

  const nav = useMemo(
    () => ({
      view,
      goHome: () => navigate({ type: "home" }),
      showProducts: () => navigate({ type: "products" }),
      showProduct: (slug) => navigate({ type: "product", slug }),
      showTeams: () => navigate({ type: "teams" }),
      showTeam: (slug) => navigate({ type: "team", slug }),
      showDemo: () => navigate({ type: "demo" }),
      isProductActive: view.type === "products" || view.type === "product",
      isTeamActive: view.type === "teams" || view.type === "team",
    }),
    [view, navigate]
  );

  useEffect(() => {
    document.title = "Incentra — Sales compensation platform";
  }, []);

  const isHome = view.type === "home";

  useEffect(() => {
    const onScroll = () => setNavScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!openMenu && !mobileNavOpen) return undefined;

    const handleClickOutside = (event) => {
      if (!event.target.closest(".marketing-nav")) {
        closeMenus();
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") closeMenus();
    };

    document.addEventListener("click", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("click", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [openMenu, mobileNavOpen, closeMenus]);

  let content = <MarketingHome />;
  if (view.type === "products") {
    content = <MarketingProductsIndex />;
  } else if (view.type === "product") {
    content = getProductArea(view.slug) ? (
      <MarketingProductPage slug={view.slug} />
    ) : (
      <MarketingProductsIndex />
    );
  } else if (view.type === "teams") {
    content = <MarketingTeamsIndex />;
  } else if (view.type === "team") {
    content = getTeamSolution(view.slug) ? (
      <MarketingTeamPage slug={view.slug} />
    ) : (
      <MarketingTeamsIndex />
    );
  } else if (view.type === "demo") {
    content = <MarketingDemo />;
  }

  return (
    <MarketingNavContext.Provider value={nav}>
      <main className="marketing-site" id="main-content">
        <a href="#main-content" className="marketing-skip">
          Skip to main content
        </a>

        <header
          className={`marketing-nav${mobileNavOpen ? " marketing-nav--open" : ""}${isHome && !navScrolled ? " marketing-nav--transparent" : ""}${navScrolled ? " marketing-nav--scrolled" : ""}`}
        >
          <button type="button" className="marketing-brand" aria-label="Incentra home" onClick={nav.goHome}>
            <img src="/incentra-icon.svg" alt="" className="marketing-brand__logo" />
            <span className="marketing-brand__name">Incentra</span>
          </button>
          <button
            type="button"
            className="marketing-nav__toggle"
            aria-expanded={mobileNavOpen}
            aria-controls="marketing-nav-menu"
            onClick={() => {
              setMobileNavOpen((open) => !open);
              setOpenMenu(null);
            }}
          >
            {mobileNavOpen ? "Close" : "Menu"}
          </button>
          <nav className="marketing-nav__links" id="marketing-nav-menu" aria-label="Marketing navigation">
            <div
              className={`marketing-nav__dropdown${nav.isProductActive ? " marketing-nav__dropdown--active" : ""}${openMenu === "product" ? " marketing-nav__dropdown--open" : ""}`}
            >
              <button
                type="button"
                className="marketing-nav__dropdown-trigger"
                aria-expanded={openMenu === "product"}
                aria-haspopup="menu"
                onClick={(event) => toggleMenu("product", event)}
              >
                Product
              </button>
              <div className="marketing-nav__menu" role="menu">
                {PRODUCT_AREAS.map((area) => (
                  <button
                    key={area.slug}
                    type="button"
                    role="menuitem"
                    onClick={handleMenuAction(() => nav.showProduct(area.slug))}
                  >
                    {area.label}
                  </button>
                ))}
              </div>
            </div>
            <div
              className={`marketing-nav__dropdown${nav.isTeamActive ? " marketing-nav__dropdown--active" : ""}${openMenu === "teams" ? " marketing-nav__dropdown--open" : ""}`}
            >
              <button
                type="button"
                className="marketing-nav__dropdown-trigger"
                aria-expanded={openMenu === "teams"}
                aria-haspopup="menu"
                onClick={(event) => toggleMenu("teams", event)}
              >
                Teams
              </button>
              <div className="marketing-nav__menu" role="menu">
                {SOLUTIONS_BY_FUNCTION.map((team) => (
                  <button
                    key={team.slug}
                    type="button"
                    role="menuitem"
                    onClick={handleMenuAction(() => nav.showTeam(team.slug))}
                  >
                    {team.label}
                  </button>
                ))}
              </div>
            </div>
            <Link to="/login" className="marketing-nav__login" onClick={closeMenus}>
              Sign in
            </Link>
            <div className="marketing-nav__actions">
              <a
                href="mailto:shivakumar@incentra.co.in?subject=Incentra%20sales%20inquiry"
                className="marketing-nav__cta-secondary"
                onClick={closeMenus}
              >
                Contact sales
              </a>
              <button type="button" className="marketing-nav__cta" onClick={nav.showDemo}>
                Request demo
              </button>
            </div>
          </nav>
        </header>

        <div key={view.type + (view.slug || "")} className="marketing-content">
          {content}
        </div>

        <footer className="marketing-footer" id="contact">
          <div className="marketing-footer__top">
            <div className="marketing-footer__brand-block">
              <button type="button" className="marketing-footer__logo" onClick={nav.goHome}>
                <img src="/incentra-icon.svg" alt="" />
                <span>Incentra</span>
              </button>
              <p>Enterprise sales compensation — plans, orders, commissions, and payroll export.</p>
              <div className="marketing-footer__social">
                <a href="mailto:shivakumar@incentra.co.in">Email</a>
                <a href="tel:+918499087617">Phone</a>
              </div>
            </div>
            <div className="marketing-footer__grid marketing-footer__grid--enterprise">
              <div className="marketing-footer__col">
                <span className="marketing-footer__col-title">Product</span>
                {PRODUCT_AREAS.map((area) => (
                  <button
                    key={area.slug}
                    type="button"
                    className="marketing-footer__link"
                    onClick={() => nav.showProduct(area.slug)}
                  >
                    {area.label}
                  </button>
                ))}
              </div>
              <div className="marketing-footer__col">
                <span className="marketing-footer__col-title">Solutions</span>
                {SOLUTIONS_BY_FUNCTION.map((team) => (
                  <button
                    key={team.slug}
                    type="button"
                    className="marketing-footer__link"
                    onClick={() => nav.showTeam(team.slug)}
                  >
                    {team.label}
                  </button>
                ))}
              </div>
              <div className="marketing-footer__col">
                <span className="marketing-footer__col-title">Resources</span>
                <button type="button" className="marketing-footer__link" onClick={nav.showDemo}>
                  Request demo
                </button>
                <button type="button" className="marketing-footer__link" onClick={nav.showProducts}>
                  Product overview
                </button>
                <button type="button" className="marketing-footer__link" onClick={nav.showTeams}>
                  Solutions by team
                </button>
              </div>
              <div className="marketing-footer__col">
                <span className="marketing-footer__col-title">Company</span>
                <a href="mailto:shivakumar@incentra.co.in" className="marketing-footer__link">
                  Contact
                </a>
                <Link to="/login" className="marketing-footer__link">
                  Sign in
                </Link>
                <button type="button" className="marketing-footer__link" onClick={nav.showDemo}>
                  Book consultation
                </button>
              </div>
              <div className="marketing-footer__col">
                <span className="marketing-footer__col-title">Legal</span>
                <span className="marketing-footer__link marketing-footer__link--muted">
                  Privacy policy
                </span>
                <span className="marketing-footer__link marketing-footer__link--muted">
                  Terms of service
                </span>
              </div>
            </div>
          </div>
          <div className="marketing-footer__bottom">
            <span>© {new Date().getFullYear()} Incentra. All rights reserved.</span>
          </div>
        </footer>
      </main>
    </MarketingNavContext.Provider>
  );
}

export default MarketingLayout;
