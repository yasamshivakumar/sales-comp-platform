import { useState, useEffect, useMemo } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  AppBar,
  Avatar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import SpaceDashboardOutlinedIcon from "@mui/icons-material/SpaceDashboardOutlined";
import AccountBalanceWalletOutlinedIcon from "@mui/icons-material/AccountBalanceWalletOutlined";
import PaymentsOutlinedIcon from "@mui/icons-material/PaymentsOutlined";
import ShoppingBagOutlinedIcon from "@mui/icons-material/ShoppingBagOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import GavelOutlinedIcon from "@mui/icons-material/GavelOutlined";
import ManageAccountsOutlinedIcon from "@mui/icons-material/ManageAccountsOutlined";
import PublicOutlinedIcon from "@mui/icons-material/PublicOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import SavingsOutlinedIcon from "@mui/icons-material/SavingsOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import VpnKeyOutlinedIcon from "@mui/icons-material/VpnKeyOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import api from "../../api";
import { useTheme as useAppTheme } from "../../ThemeContext";
import { enterprise } from "../../theme/muiTheme";
import ChangePassword from "../ChangePassword";
import "../enterprise.css";

const DRAWER_WIDTH = 108;

const sidebarBg = `linear-gradient(180deg, ${enterprise.navy} 0%, ${enterprise.navyDark} 100%)`;

const drawerPaperSx = {
  width: DRAWER_WIDTH,
  boxSizing: "border-box",
  borderRight: "none",
  background: sidebarBg,
  color: "rgba(255,255,255,0.82)",
  boxShadow: "4px 0 24px rgba(0, 0, 0, 0.18)",
  "& .MuiDivider-root": {
    borderColor: "rgba(255,255,255,0.1)",
  },
};

const navItemSx = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  textAlign: "center",
  width: "100%",
  py: 1,
  px: 0.5,
  gap: 0.4,
  minHeight: 56,
  borderRadius: 1.5,
  color: "rgba(255,255,255,0.62)",
  border: "1px solid transparent",
  borderLeft: "3px solid transparent",
  backgroundColor: "transparent",
  cursor: "pointer",
  textDecoration: "none",
  outline: "none",
  WebkitTapHighlightColor: "transparent",
  transition: "color 0.15s ease, background-color 0.15s ease",
  "&:hover": {
    backgroundColor: "transparent",
    color: "inherit",
    textDecoration: "none",
  },
  "&:focus-visible": {
    outline: "1px solid rgba(255,255,255,0.35)",
    outlineOffset: 0,
  },
  "&.sidebar-nav-item--active": {
    backgroundColor: "rgba(255,255,255,0.12)",
    color: "#fff",
    borderColor: "rgba(255,255,255,0.18)",
    borderLeftColor: "#fff",
    "&:hover": {
      backgroundColor: "rgba(255,255,255,0.12)",
      color: "#fff",
    },
  },
};

const navLabelSx = {
  fontSize: 10,
  fontWeight: 700,
  lineHeight: 1.15,
  display: "block",
  whiteSpace: "normal",
  wordBreak: "break-word",
  maxWidth: "100%",
};

function NavItemButton({ icon: Icon, label, selected, onClick, to, component, compact = false, className: extraClass = "", sx = {} }) {
  const itemSx = compact
    ? {
        ...navItemSx,
        minHeight: 40,
        py: 0.5,
        px: 0.25,
        gap: 0.25,
      }
    : navItemSx;
  const iconSize = compact ? 16 : 20;
  const labelSx = compact
    ? { ...navLabelSx, fontSize: 8, lineHeight: 1.1 }
    : navLabelSx;

  const className = `sidebar-nav-item${selected ? " sidebar-nav-item--active" : ""}${extraClass ? ` ${extraClass}` : ""}`;
  const content = (
    <>
      <Icon sx={{ fontSize: iconSize, display: "block" }} />
      <Typography component="span" sx={labelSx}>
        {label}
      </Typography>
    </>
  );

  if (component === Link && to) {
    return (
      <Box
        component={Link}
        to={to}
        onClick={onClick}
        className={className}
        sx={{ ...itemSx, ...sx }}
      >
        {content}
      </Box>
    );
  }

  return (
    <Box
      component="button"
      type="button"
      onClick={onClick}
      className={className}
      sx={{
        ...itemSx,
        ...sx,
        font: "inherit",
        appearance: "none",
      }}
    >
      {content}
    </Box>
  );
}

const repMenu = [
  { name: "Incentive Details", path: "/statement", icon: AccountBalanceWalletOutlinedIcon },
];

/** Enterprise ICM order: insight → transactions → payroll → payout → plan design → org data → compliance */
const adminMenu = [
  { name: "Dashboard", path: "/", icon: SpaceDashboardOutlinedIcon },
  { name: "Orders", path: "/orders", icon: ShoppingBagOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Payouts", path: "/payouts", icon: SavingsOutlinedIcon },
  { name: "Comp Plans", path: "/comp-plans", icon: DescriptionOutlinedIcon },
  { name: "Commission Rules", path: "/commission-rules", icon: GavelOutlinedIcon },
  { name: "User Setup", path: "/user-setup", icon: ManageAccountsOutlinedIcon },
  { name: "Territories", path: "/territories", icon: PublicOutlinedIcon },
  { name: "Audit Log", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

const financeMenu = [
  { name: "Dashboard", path: "/", icon: SpaceDashboardOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Payouts", path: "/payouts", icon: SavingsOutlinedIcon },
  { name: "Audit Log", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

const managerMenu = [
  { name: "Dashboard", path: "/", icon: SpaceDashboardOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Audit Log", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

function getMenuItems(profile) {
  if (!profile) return [{ name: "Dashboard", path: "/", icon: SpaceDashboardOutlinedIcon }];
  if (profile.is_admin) return adminMenu;
  if (profile.is_finance) return financeMenu;
  if (profile.is_manager) return managerMenu;
  return repMenu;
}

function NavList({ items, location, onNavigate }) {
  return (
    <List sx={{ px: 0.75, py: 0.5, display: "flex", flexDirection: "column", gap: 0.5 }}>
      {items.map((item) => {
        const isActive =
          location.pathname === item.path ||
          (item.path !== "/" && location.pathname.startsWith(item.path));
        return (
          <NavItemButton
            key={item.path}
            icon={item.icon}
            label={item.name}
            component={Link}
            to={item.path}
            selected={isActive}
            onClick={onNavigate}
          />
        );
      })}
    </List>
  );
}

function AppTopBar({ pageTitle, displayName, initials }) {
  return (
    <Box
      sx={{
        display: { xs: "none", md: "flex" },
        alignItems: "center",
        justifyContent: "space-between",
        px: 3,
        py: 1.5,
        minHeight: 56,
        bgcolor: "background.paper",
        borderBottom: "1px solid",
        borderColor: "divider",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <Typography variant="subtitle2" color="text.secondary" sx={{ letterSpacing: "0.04em" }}>
        INCENTRA / {pageTitle?.toUpperCase()}
      </Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
        <Typography variant="body2" color="text.secondary" fontWeight={600}>
          {displayName}
        </Typography>
        <Avatar sx={{ width: 32, height: 32, fontSize: 12, bgcolor: "primary.main" }}>
          {initials}
        </Avatar>
      </Box>
    </Box>
  );
}

function AppLayout({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const { isDarkMode, toggleTheme } = useAppTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    api.get("user-profile/").then((res) => setProfile(res.data)).catch(() => setProfile(null));
  }, []);

  useEffect(() => {
    if (searchParams.get("integrations") === "1") {
      navigate("/orders?tab=connect", { replace: true });
    }
  }, [searchParams, navigate]);

  const menuItems = getMenuItems(profile);
  const displayName = profile?.name || localStorage.getItem("name") || "User";
  const initials = displayName.slice(0, 2).toUpperCase();

  const pageTitle = useMemo(() => {
    const match = menuItems.find(
      (item) =>
        location.pathname === item.path ||
        (item.path !== "/" && location.pathname.startsWith(item.path))
    );
    return match?.name || "Workspace";
  }, [location.pathname, menuItems]);

  const logout = () => {
    localStorage.clear();
    window.location.href = "/login";
  };

  const drawerContent = (
    <Box className="enterprise-sidebar" sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ px: 1, pt: 2, pb: 1, textAlign: "center", position: "relative" }}>
        <Avatar
          sx={{
            bgcolor: enterprise.accent,
            width: 40,
            height: 40,
            mx: "auto",
            mb: 0.75,
            boxShadow: "0 4px 14px rgba(1,118,211,0.45)",
          }}
        >
          <InsightsOutlinedIcon />
        </Avatar>
        <Typography variant="caption" fontWeight={800} display="block" lineHeight={1.2} color="#fff">
          Incentra
        </Typography>
        {isMobile && (
          <IconButton
            size="small"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
            sx={{ position: "absolute", right: 4, top: 4, color: "#fff" }}
          >
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
        )}
      </Box>

      <Divider sx={{ my: 1 }} />

      <Box sx={{ flex: 1, overflowY: "auto" }}>
        <NavList
          items={menuItems}
          location={location}
          onNavigate={() => isMobile && setMobileOpen(false)}
        />
      </Box>

      <Divider />
      <List sx={{ px: 0.5, py: 0.5, display: "flex", flexDirection: "column", gap: 0.25 }}>
        <NavItemButton
          compact
          icon={VpnKeyOutlinedIcon}
          label="Password"
          onClick={() => setShowChangePassword(true)}
        />
        <NavItemButton
          compact
          icon={isDarkMode ? DarkModeOutlinedIcon : LightModeOutlinedIcon}
          label={isDarkMode ? "Dark" : "Light"}
          onClick={toggleTheme}
        />
        <NavItemButton
          compact
          className="sidebar-nav-item--logout"
          icon={LogoutOutlinedIcon}
          label="Logout"
          onClick={logout}
        />
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          display: { md: "none" },
          bgcolor: enterprise.navy,
          color: "#fff",
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <Toolbar>
          <IconButton edge="start" onClick={() => setMobileOpen(true)} aria-label="Open menu" sx={{ color: "#fff" }}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1, fontWeight: 800, flexGrow: 1 }}>
            Incentra
          </Typography>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          PaperProps={{ className: "enterprise-sidebar" }}
          sx={{
            display: { xs: "block", md: "none" },
            "& .MuiDrawer-paper": { ...drawerPaperSx, width: 120 },
          }}
        >
          {drawerContent}
        </Drawer>
        <Drawer
          variant="permanent"
          PaperProps={{ className: "enterprise-sidebar" }}
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": drawerPaperSx,
          }}
          open
        >
          {drawerContent}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          pt: { xs: 8, md: 0 },
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <AppTopBar
          pageTitle={pageTitle}
          displayName={displayName}
          initials={initials}
        />
        <Box
          className="container-fluid"
          sx={{
            flex: 1,
            px: { xs: 2, sm: 3 },
            py: { xs: 2, sm: 3 },
            maxWidth: 1600,
            mx: "auto",
            width: "100%",
          }}
        >
          {children}
        </Box>
      </Box>

      {showChangePassword && <ChangePassword onClose={() => setShowChangePassword(false)} />}
    </Box>
  );
}

export default AppLayout;
