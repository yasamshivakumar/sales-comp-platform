import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import ChangePassword from "./ChangePassword";
import { useTheme } from "../ThemeContext";
import api from "../api";

const adminMenuItems = [
  { name: "User Setup", path: "/user-setup", icon: "👥" },
  { name: "Dashboard", path: "/", icon: "🏠" },
  { name: "Commissions", path: "/commissions", icon: "💰" },
  { name: "Comp Plans", path: "/comp-plans", icon: "📊" },
  { name: "Orders", path: "/orders", icon: "📦" },
];

const employeeMenuItems = [
  { name: "Commissions", path: "/commissions", icon: "💰" },
];

function Sidebar() {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(true);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  const { isDarkMode, toggleTheme } = useTheme();

  useEffect(() => {
    fetchUserRole();
  }, []);

  useEffect(() => {
    document.body.classList.toggle("sidebar-collapsed", !isOpen);
    return () => document.body.classList.remove("sidebar-collapsed");
  }, [isOpen]);

  const fetchUserRole = async () => {
    try {
      const response = await api.get("user-profile/");
      const adminRoles = ["admin", "administrator"];
      setIsAdmin(adminRoles.includes(response.data.role?.toLowerCase()));
    } catch {
      setIsAdmin(false);
    }
  };

  const menuItems = isAdmin ? adminMenuItems : employeeMenuItems;

  const logout = () => {
    localStorage.clear();
    window.location.href = "/login";
  };

  const sidebarClass = `sidebar${isOpen ? "" : " sidebar--collapsed"}`;

  return (
    <>
      <aside className={sidebarClass}>
        <div className="sidebar__header">
          <div className="sidebar__brand">
            <div className="sidebar__logo-icon" aria-hidden="true">
              ⚡
            </div>
            {isOpen && (
              <h2 className="sidebar__logo-text">IncentivePro</h2>
            )}
          </div>
          <button
            type="button"
            className="sidebar__toggle"
            onClick={() => setIsOpen(!isOpen)}
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
            title={isOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {isOpen ? "◀" : "▶"}
          </button>
        </div>

        {isOpen && (
          <div className="sidebar__role">
            {isAdmin ? "👑 Administrator" : "👤 Sales Rep"}
          </div>
        )}

        <nav className="sidebar__nav">
          {menuItems.map((item) => {
            const isActive =
              location.pathname === item.path ||
              (item.path !== "/" && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`sidebar__link${isActive ? " sidebar__link--active" : ""}`}
                title={item.name}
              >
                <span className="sidebar__link-icon">{item.icon}</span>
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar__footer">
          <button
            type="button"
            className="sidebar__btn sidebar__btn--ghost"
            onClick={() => setShowChangePassword(true)}
          >
            <span className="sidebar__link-icon">🔐</span>
            <span>{isOpen ? "Change Password" : ""}</span>
          </button>
          <button
            type="button"
            className="sidebar__btn sidebar__btn--theme"
            onClick={toggleTheme}
          >
            <span className="sidebar__link-icon">{isDarkMode ? "🌙" : "☀️"}</span>
            <span>{isOpen ? (isDarkMode ? "Dark Mode" : "Light Mode") : ""}</span>
          </button>
          <button
            type="button"
            className="sidebar__btn sidebar__btn--logout"
            onClick={logout}
          >
            <span className="sidebar__link-icon">🚪</span>
            <span>{isOpen ? "Logout" : ""}</span>
          </button>
        </div>
      </aside>

      {showChangePassword && (
        <ChangePassword onClose={() => setShowChangePassword(false)} />
      )}
    </>
  );
}

export default Sidebar;
