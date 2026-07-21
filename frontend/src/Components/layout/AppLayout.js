import { useState, useEffect, useMemo } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Divider,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  IconButton,
  List,
  Stack,
  Toolbar,
  Typography,
  Tooltip,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import MenuIcon from "@mui/icons-material/Menu";
import SpaceDashboardOutlinedIcon from "@mui/icons-material/SpaceDashboardOutlined";
import AccountBalanceWalletOutlinedIcon from "@mui/icons-material/AccountBalanceWalletOutlined";
import PaymentsOutlinedIcon from "@mui/icons-material/PaymentsOutlined";
import ShoppingBagOutlinedIcon from "@mui/icons-material/ShoppingBagOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import GavelOutlinedIcon from "@mui/icons-material/GavelOutlined";
import ManageAccountsOutlinedIcon from "@mui/icons-material/ManageAccountsOutlined";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import SavingsOutlinedIcon from "@mui/icons-material/SavingsOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import VpnKeyOutlinedIcon from "@mui/icons-material/VpnKeyOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import api, {
  enforceValidSession,
  getAuthSessionValue,
  performLogout,
} from "../../api";
import { useTheme as useAppTheme } from "../../ThemeContext";
import { enterprise } from "../../theme/muiTheme";
import AuthTextField from "../AuthTextField";
import ChangePassword from "../ChangePassword";
import Integrations from "../../Enterprise/Integrations";
import { useToast } from "../Toast";
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
  { name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon },
  { name: "Sales insights", path: "/sales-insights", icon: MapOutlinedIcon },
  { name: "Orders", path: "/orders", icon: ShoppingBagOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Payouts", path: "/payouts", icon: SavingsOutlinedIcon },
  { name: "Comp Plans", path: "/comp-plans", icon: DescriptionOutlinedIcon },
  { name: "Commission Rules", path: "/commission-rules", icon: GavelOutlinedIcon },
  { name: "User Setup", path: "/user-setup", icon: ManageAccountsOutlinedIcon },
  { name: "Audit Log", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

const financeMenu = [
  { name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon },
  { name: "Sales insights", path: "/sales-insights", icon: MapOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Payouts", path: "/payouts", icon: SavingsOutlinedIcon },
  { name: "Audit Log", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

const managerMenu = [
  { name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon },
  { name: "Sales insights", path: "/sales-insights", icon: MapOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Audit Log", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

function getMenuItems(profile) {
  if (!profile) return [{ name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon }];
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

function AppTopBar({ pageTitle, displayName, initials, profile, onEditProfile, showConnect, onOpenConnect }) {
  const roleLabel = profile?.role || "Workspace user";
  const organizationLabel = profile?.organization_name || profile?.organization_slug || "";

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
              <HubOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Box
          component="button"
          type="button"
          className="app-profile-chip"
          onClick={onEditProfile}
          aria-label="Edit profile details"
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
            "& .MuiTypography-root": {
              color: "inherit",
            },
            "&:hover": {
              borderColor: "primary.main",
              transform: "none",
            },
            "&:focus-visible": {
              outline: "2px solid",
              outlineColor: "primary.main",
              outlineOffset: 2,
            },
          }}
        >
          <Box sx={{ minWidth: 0, textAlign: "right" }}>
            <Typography
              variant="body2"
              fontWeight={800}
              noWrap
              sx={{ maxWidth: 180, lineHeight: 1.15, color: "inherit" }}
            >
              {displayName}
            </Typography>
            <Typography
              variant="caption"
              noWrap
              sx={{
                display: "block",
                maxWidth: 180,
                lineHeight: 1.15,
                color: "text.secondary",
                opacity: 0.92,
              }}
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
              boxShadow: "0 6px 16px rgba(25, 118, 210, 0.28)",
            }}
          >
            {initials}
          </Avatar>
        </Box>
      </Box>
    </Box>
  );
}

function AppLayout({ children }) {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const { isDarkMode, toggleTheme } = useAppTheme();
  const { success, error } = useToast();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [profile, setProfile] = useState(null);
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const [connectDialogOpen, setConnectDialogOpen] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileForm, setProfileForm] = useState({
    name: "",
    first_name: "",
    last_name: "",
  });

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
    if (!profile) return;
    setProfileForm({
      name: profile.name || "",
      first_name: profile.first_name || "",
      last_name: profile.last_name || "",
    });
  }, [profile]);

  useEffect(() => {
    if (searchParams.get("integrations") === "1" && profile?.is_admin) {
      setConnectDialogOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete("integrations");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams, profile?.is_admin]);

  const canManageIntegrations = Boolean(profile?.is_admin);

  const menuItems = getMenuItems(profile);
  const displayName = profile?.name || getAuthSessionValue("name") || "User";
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "U";

  const pageTitle = useMemo(() => {
    const match = menuItems.find(
      (item) =>
        location.pathname === item.path ||
        (item.path !== "/" && location.pathname.startsWith(item.path))
    );
    return match?.name || "Workspace";
  }, [location.pathname, menuItems]);

  const logout = () => {
    performLogout();
  };

  const openProfileDialog = () => {
    if (profile) {
      setProfileForm({
        name: profile.name || "",
        first_name: profile.first_name || "",
        last_name: profile.last_name || "",
      });
    }
    setProfileDialogOpen(true);
  };

  const saveProfile = async () => {
    const payload = {
      name: profileForm.name.trim(),
      first_name: profileForm.first_name.trim(),
      last_name: profileForm.last_name.trim(),
    };
    if (!payload.name) {
      error({
        title: "Name required",
        message: "Enter the display name you want shown in the profile icon.",
      });
      return;
    }

    setProfileSaving(true);
    try {
      const response = await api.patch("user-profile/", payload);
      setProfile(response.data);
      sessionStorage.setItem("name", response.data.name || "");
      setProfileDialogOpen(false);
      success({
        title: "Profile updated",
        message: "Your profile details were saved.",
      });
    } catch (err) {
      error({
        title: "Profile update failed",
        message: err.response?.data?.error || "Could not save your profile details.",
      });
    } finally {
      setProfileSaving(false);
    }
  };

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
    <Box
      sx={{
        display: "flex",
        minHeight: "100vh",
        width: "100%",
        maxWidth: "100vw",
        minWidth: 0,
        overflowX: "hidden",
        bgcolor: "background.default",
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
        }}
      >
        <Toolbar>
          <IconButton edge="start" onClick={() => setMobileOpen(true)} aria-label="Open menu" sx={{ color: "#fff" }}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1, fontWeight: 800, flexGrow: 1 }}>
            Incentra
          </Typography>
          {canManageIntegrations && (
            <Tooltip title="Connect CRM">
              <IconButton
                onClick={() => setConnectDialogOpen(true)}
                aria-label="Connect CRM"
                sx={{
                  color: "#fff",
                  border: "1px solid rgba(255,255,255,0.22)",
                  mr: 0.5,
                  "&:hover": {
                    bgcolor: "rgba(255,255,255,0.08)",
                  },
                }}
              >
                <HubOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <IconButton
            onClick={openProfileDialog}
            aria-label="Edit profile details"
            sx={{
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.22)",
              borderRadius: 999,
              gap: 1,
              px: 1,
              py: 0.5,
              maxWidth: "52vw",
              "&:hover": {
                bgcolor: "rgba(255,255,255,0.08)",
              },
            }}
          >
            <Box sx={{ minWidth: 0, textAlign: "right", display: { xs: "none", sm: "block" } }}>
              <Typography
                variant="caption"
                noWrap
                sx={{ display: "block", lineHeight: 1.1, fontWeight: 800, color: "inherit" }}
              >
                {displayName}
              </Typography>
              <Typography
                variant="caption"
                noWrap
                sx={{ display: "block", lineHeight: 1.1, color: "inherit", opacity: 0.82 }}
              >
                {profile?.organization_name || profile?.organization_slug || profile?.role || "Profile"}
              </Typography>
            </Box>
            <Avatar sx={{ width: 28, height: 28, fontSize: 10, bgcolor: enterprise.accent }}>
              {initials}
            </Avatar>
          </IconButton>
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
          width: { xs: "100%", md: `calc(100% - ${DRAWER_WIDTH}px)` },
          maxWidth: "100%",
          minWidth: 0,
          overflowX: "hidden",
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
          profile={profile}
          onEditProfile={openProfileDialog}
          showConnect={canManageIntegrations}
          onOpenConnect={() => setConnectDialogOpen(true)}
        />
        <Box
          className="container-fluid"
          sx={{
            flex: 1,
            px: { xs: 2, sm: 3 },
            py: { xs: 2, sm: 3 },
            maxWidth: "none",
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
      <Dialog
        open={profileDialogOpen}
        onClose={() => !profileSaving && setProfileDialogOpen(false)}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            bgcolor: "background.paper",
            backgroundImage: "none",
          },
        }}
      >
        <DialogTitle>Edit profile details</DialogTitle>
        <DialogContent sx={{ color: "text.primary" }}>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <AuthTextField
              label="Company"
              value={profile?.organization_name || profile?.organization_slug || ""}
              disabled
              helperText="Company is managed by your workspace admin."
            />
            <AuthTextField
              label="Display name"
              value={profileForm.name}
              onChange={(e) =>
                setProfileForm((current) => ({ ...current, name: e.target.value }))
              }
              autoFocus
            />
            <AuthTextField
              label="First name"
              value={profileForm.first_name}
              onChange={(e) =>
                setProfileForm((current) => ({ ...current, first_name: e.target.value }))
              }
            />
            <AuthTextField
              label="Last name"
              value={profileForm.last_name}
              onChange={(e) =>
                setProfileForm((current) => ({ ...current, last_name: e.target.value }))
              }
            />
            <AuthTextField label="Email" value={profile?.email || ""} disabled />
            <AuthTextField label="Role" value={profile?.role || ""} disabled />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProfileDialogOpen(false)} disabled={profileSaving}>
            Cancel
          </Button>
          <Button variant="contained" onClick={saveProfile} disabled={profileSaving}>
            {profileSaving ? "Saving..." : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={connectDialogOpen}
        onClose={() => setConnectDialogOpen(false)}
        fullWidth
        maxWidth="lg"
        scroll="paper"
        aria-labelledby="integrations-dialog-title"
        PaperProps={{
          sx: {
            bgcolor: "background.paper",
            backgroundImage: "none",
            border: "1px solid",
            borderColor: "divider",
          },
        }}
      >
        <DialogContent sx={{ p: { xs: 2, sm: 3 }, bgcolor: "background.paper" }}>
          <Integrations
            embedded
            inline
            onClose={() => setConnectDialogOpen(false)}
            onOrdersSynced={(data) => {
              const count = data?.result?.success ?? 0;
              if (count > 0) {
                success(`Synced ${count} order(s) from CRM — check Orders for results.`);
              }
            }}
          />
        </DialogContent>
      </Dialog>
    </Box>
  );
}

export default AppLayout;
