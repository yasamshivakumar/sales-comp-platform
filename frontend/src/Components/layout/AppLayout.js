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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Tooltip,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import CloudSyncOutlinedIcon from "@mui/icons-material/CloudSyncOutlined";
import MenuIcon from "@mui/icons-material/Menu";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import VpnKeyOutlinedIcon from "@mui/icons-material/VpnKeyOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import PersonOutlineOutlinedIcon from "@mui/icons-material/PersonOutlineOutlined";
import TuneOutlinedIcon from "@mui/icons-material/TuneOutlined";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import api, {
  enforceValidSession,
  getAuthSessionValue,
  performLogout,
} from "../../api";
import { useTheme as useAppTheme } from "../../ThemeContext";
import { enterprise } from "../../theme/muiTheme";
import ChangePassword from "../ChangePassword";
import { getMenuItems, resolvePageTitle } from "./navConfig";
import { GlobalSearch } from "../enterprise";
import "../enterprise.css";
import "../../styles/layout-containment.css";

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

function AppTopBar({
  pageTitle,
  displayName,
  initials,
  profile,
  menuAnchor,
  onOpenMenu,
  onCloseMenu,
  onProfile,
  onPreferences,
  onPassword,
  onSignOut,
  showConnect,
  onOpenConnect,
}) {
  const roleLabel = profile?.role || "Workspace user";
  const organizationLabel = profile?.organization_name || profile?.organization_slug || "";

  return (
    <Box
      className="app-glass-topbar"
      sx={{
        display: { xs: "none", md: "flex" },
        alignItems: "center",
        justifyContent: "space-between",
        px: 3,
        py: 1.5,
        minHeight: 56,
        bgcolor: "transparent",
        borderBottom: "1px solid",
        borderColor: "divider",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <GlobalSearch profile={profile} />
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        {showConnect && (
          <Tooltip title="Connect CRM">
            <IconButton
              onClick={onOpenConnect}
              aria-label="Connect CRM"
              sx={{
                border: "1px solid",
                borderColor: "divider",
                bgcolor: "background.default",
                boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
                "&:hover": {
                  borderColor: "primary.main",
                  bgcolor: "action.hover",
                },
              }}
            >
              <CloudSyncOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Box
          component="button"
          type="button"
          className="app-profile-chip"
          onClick={onOpenMenu}
          aria-label="Account menu"
          aria-haspopup="menu"
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.25,
            minWidth: 0,
            px: 1.25,
            py: 0.65,
            borderRadius: 999,
            border: "1px solid",
            borderColor: "divider",
            bgcolor: "background.default",
            color: "text.primary",
            boxShadow: (theme) =>
              theme.palette.mode === "dark"
                ? "0 8px 24px rgba(0, 0, 0, 0.35)"
                : "0 8px 24px rgba(15, 23, 42, 0.06)",
            cursor: "pointer",
            font: "inherit",
            textAlign: "inherit",
            "&:hover": { borderColor: "primary.main" },
          }}
        >
          <Box sx={{ minWidth: 0, textAlign: "right" }}>
            <Typography variant="body2" fontWeight={800} noWrap sx={{ maxWidth: 180, lineHeight: 1.15 }}>
              {displayName}
            </Typography>
            <Typography
              variant="caption"
              noWrap
              sx={{ display: "block", maxWidth: 180, lineHeight: 1.15, color: "text.secondary" }}
            >
              {organizationLabel ? `${roleLabel} · ${organizationLabel}` : roleLabel}
            </Typography>
          </Box>
          <Avatar
            sx={{
              width: 36,
              height: 36,
              fontSize: 12,
              fontWeight: 800,
              bgcolor: "primary.main",
              color: "primary.contrastText",
            }}
          >
            {initials}
          </Avatar>
        </Box>
        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={onCloseMenu}
          anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
          transformOrigin={{ vertical: "top", horizontal: "right" }}
        >
          <MenuItem
            onClick={() => {
              onCloseMenu();
              onProfile();
            }}
          >
            <ListItemIcon>
              <PersonOutlineOutlinedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>My Profile</ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              onCloseMenu();
              onPreferences();
            }}
          >
            <ListItemIcon>
              <TuneOutlinedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>My Preferences</ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              onCloseMenu();
              onPassword();
            }}
          >
            <ListItemIcon>
              <VpnKeyOutlinedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Change Password</ListItemText>
          </MenuItem>
          <Divider />
          <MenuItem
            onClick={() => {
              onCloseMenu();
              onSignOut();
            }}
          >
            <ListItemIcon>
              <LogoutOutlinedIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText>Sign Out</ListItemText>
          </MenuItem>
        </Menu>
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
  const [menuAnchor, setMenuAnchor] = useState(null);

  useEffect(() => {
    if (!enforceValidSession()) return undefined;
    let cancelled = false;
    api
      .get("user-profile/")
      .then((res) => {
        if (!cancelled) setProfile(res.data);
      })
      .catch(() => {
        if (!cancelled) setProfile(null);
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  useEffect(() => {
    const onSessionEnd = () => setProfile(null);
    window.addEventListener("session-expired", onSessionEnd);
    window.addEventListener("unauthorized", onSessionEnd);
    return () => {
      window.removeEventListener("session-expired", onSessionEnd);
      window.removeEventListener("unauthorized", onSessionEnd);
    };
  }, []);

  useEffect(() => {
    if (searchParams.get("integrations") === "1" && profile?.is_admin) {
      const next = new URLSearchParams(searchParams);
      next.delete("integrations");
      setSearchParams(next, { replace: true });
      navigate("/integrations");
    }
  }, [searchParams, setSearchParams, profile?.is_admin, navigate]);

  const canManageIntegrations = Boolean(profile?.is_admin);
  const menuItems = getMenuItems(profile);
  const displayName = profile?.name || getAuthSessionValue("name") || "User";
  const initials =
    displayName
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "U";

  const pageTitle = useMemo(
    () => resolvePageTitle(location.pathname, menuItems),
    [location.pathname, menuItems]
  );

  const logout = () => {
    performLogout();
  };

  const openAccountMenu = (event) => setMenuAnchor(event.currentTarget);
  const closeAccountMenu = () => setMenuAnchor(null);

  const drawerContent = (
    <Box className="enterprise-sidebar" sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ px: 1, pt: 2, pb: 1, textAlign: "center", position: "relative" }}>
        <Box
          component="img"
          src="/incentra-icon.svg"
          alt=""
          sx={{
            width: 40,
            height: 40,
            display: "block",
            mx: "auto",
            mb: 0.75,
            borderRadius: 1.5,
            boxShadow: "0 4px 14px rgba(1,118,211,0.45)",
          }}
        />
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
          icon={isDarkMode ? DarkModeOutlinedIcon : LightModeOutlinedIcon}
          label={isDarkMode ? "Dark" : "Light"}
          onClick={toggleTheme}
        />
      </List>
    </Box>
  );

  return (
    <Box
      className="app-glass-shell"
      sx={{
        display: "flex",
        minHeight: "100vh",
        width: "100%",
        maxWidth: "100vw",
        minWidth: 0,
        overflowX: "hidden",
        bgcolor: "transparent",
      }}
    >
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          display: { md: "none" },
          bgcolor: enterprise.navy,
          color: "#fff",
          borderBottom: "1px solid rgba(255,255,255,0.1)",
          pt: "env(safe-area-inset-top)",
        }}
      >
        <Toolbar sx={{ minHeight: { xs: 56 }, gap: 0.5 }}>
          <IconButton edge="start" onClick={() => setMobileOpen(true)} aria-label="Open menu" sx={{ color: "#fff" }}>
            <MenuIcon />
          </IconButton>
          <Box sx={{ ml: 0.5, flexGrow: 1, minWidth: 0 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 800, lineHeight: 1.15 }} noWrap>
              {pageTitle}
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.75, lineHeight: 1.1, display: "block" }} noWrap>
              Incentra
            </Typography>
          </Box>
          {canManageIntegrations && (
            <Tooltip title="Connect CRM">
              <IconButton
                onClick={() => navigate("/integrations")}
                aria-label="Connect CRM"
                sx={{
                  color: "#fff",
                  border: "1px solid rgba(255,255,255,0.22)",
                  mr: 0.5,
                }}
              >
                <CloudSyncOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <IconButton
            onClick={openAccountMenu}
            aria-label="Account menu"
            sx={{
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.22)",
              borderRadius: 999,
              px: 1,
              py: 0.5,
            }}
          >
            <Avatar sx={{ width: 28, height: 28, fontSize: 10, bgcolor: enterprise.accent }}>
              {initials}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={closeAccountMenu}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            <MenuItem
              onClick={() => {
                closeAccountMenu();
                navigate("/profile");
              }}
            >
              <ListItemText>My Profile</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                closeAccountMenu();
                navigate("/profile/preferences");
              }}
            >
              <ListItemText>My Preferences</ListItemText>
            </MenuItem>
            <MenuItem
              onClick={() => {
                closeAccountMenu();
                setShowChangePassword(true);
              }}
            >
              <ListItemText>Change Password</ListItemText>
            </MenuItem>
            <Divider />
            <MenuItem
              onClick={() => {
                closeAccountMenu();
                logout();
              }}
            >
              <ListItemText>Sign Out</ListItemText>
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Mobile drawer */}
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

      {/* Desktop sidebar — plain Box so it stays in document flow (no content under rail) */}
      <Box
        component="nav"
        className="app-sidebar-slot enterprise-sidebar"
        sx={{
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          width: DRAWER_WIDTH,
          minWidth: DRAWER_WIDTH,
          maxWidth: DRAWER_WIDTH,
          flexShrink: 0,
          height: "100vh",
          position: "sticky",
          top: 0,
          zIndex: 1200,
          boxSizing: "border-box",
          borderRight: "none",
          background: sidebarBg,
          color: "rgba(255,255,255,0.82)",
          boxShadow: "4px 0 24px rgba(0, 0, 0, 0.18)",
          overflowX: "hidden",
          overflowY: "auto",
          "& .MuiDivider-root": { borderColor: "rgba(255,255,255,0.1)" },
        }}
      >
        {drawerContent}
      </Box>

      <Box
        component="main"
        className="app-main-content"
        sx={{
          flex: "1 1 0%",
          width: { xs: "100%", md: `calc(100% - ${DRAWER_WIDTH}px)` },
          maxWidth: { xs: "100%", md: `calc(100vw - ${DRAWER_WIDTH}px)` },
          minWidth: 0,
          overflow: "hidden",
          pt: { xs: "calc(56px + env(safe-area-inset-top))", md: 0 },
          pb: { xs: "env(safe-area-inset-bottom)", md: 0 },
          minHeight: "100dvh",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          zIndex: 1,
        }}
      >
        <AppTopBar
          pageTitle={pageTitle}
          displayName={displayName}
          initials={initials}
          profile={profile}
          menuAnchor={menuAnchor}
          onOpenMenu={openAccountMenu}
          onCloseMenu={closeAccountMenu}
          onProfile={() => navigate("/profile")}
          onPreferences={() => navigate("/profile/preferences")}
          onPassword={() => setShowChangePassword(true)}
          onSignOut={logout}
          showConnect={canManageIntegrations}
          onOpenConnect={() => navigate("/integrations")}
        />
        <Box
          className="container-fluid app-page-canvas"
          sx={{
            flex: 1,
            px: { xs: 2, sm: 3 },
            py: { xs: 2, sm: 3 },
            maxWidth: "100%",
            mx: 0,
            width: "100%",
            minWidth: 0,
            overflowX: "hidden",
            boxSizing: "border-box",
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
