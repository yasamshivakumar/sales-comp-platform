import SpaceDashboardOutlinedIcon from "@mui/icons-material/SpaceDashboardOutlined";
import AccountBalanceWalletOutlinedIcon from "@mui/icons-material/AccountBalanceWalletOutlined";
import PaymentsOutlinedIcon from "@mui/icons-material/PaymentsOutlined";
import ShoppingBagOutlinedIcon from "@mui/icons-material/ShoppingBagOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import GavelOutlinedIcon from "@mui/icons-material/GavelOutlined";
import ManageAccountsOutlinedIcon from "@mui/icons-material/ManageAccountsOutlined";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import SavingsOutlinedIcon from "@mui/icons-material/SavingsOutlined";

/**
 * Enterprise ICM navigation — personal account lives in the avatar menu only.
 */
export const PATH_TITLES = {
  "/dashboard": "Dashboard",
  "/orders": "Orders",
  "/commissions": "Commissions",
  "/payouts": "Payouts",
  "/comp-plans": "Compensation Plans",
  "/commission-rules": "Commission Rules",
  "/analytics": "Analytics",
  "/user-setup": "People & Access",
  "/audit-logs": "Activity & Compliance",
  "/integrations": "CRM Integrations",
  "/profile": "My Profile",
  "/profile/preferences": "My Preferences",
  "/statement": "Incentive Details",
};

const repMenu = [
  { name: "Incentive Details", path: "/statement", icon: AccountBalanceWalletOutlinedIcon },
  { name: "Analytics", path: "/analytics", icon: InsightsOutlinedIcon },
];

const adminMenu = [
  { name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon },
  { name: "Orders", path: "/orders", icon: ShoppingBagOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Payouts", path: "/payouts", icon: SavingsOutlinedIcon },
  { name: "Compensation Plans", path: "/comp-plans", icon: DescriptionOutlinedIcon },
  { name: "Commission Rules", path: "/commission-rules", icon: GavelOutlinedIcon },
  { name: "Analytics", path: "/analytics", icon: InsightsOutlinedIcon },
  { name: "People & Access", path: "/user-setup", icon: ManageAccountsOutlinedIcon },
  { name: "Activity & Compliance", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

const financeMenu = [
  { name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Payouts", path: "/payouts", icon: SavingsOutlinedIcon },
  { name: "Analytics", path: "/analytics", icon: InsightsOutlinedIcon },
  { name: "Activity & Compliance", path: "/audit-logs", icon: FactCheckOutlinedIcon },
];

const managerMenu = [
  { name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon },
  { name: "Commissions", path: "/commissions", icon: PaymentsOutlinedIcon },
  { name: "Analytics", path: "/analytics", icon: InsightsOutlinedIcon },
];

export function getMenuItems(profile) {
  if (!profile) {
    return [{ name: "Dashboard", path: "/dashboard", icon: SpaceDashboardOutlinedIcon }];
  }
  if (profile.is_admin) return adminMenu;
  if (profile.is_finance) return financeMenu;
  if (profile.is_manager) return managerMenu;
  return repMenu;
}

export function resolvePageTitle(pathname, menuItems) {
  const match = (menuItems || []).find(
    (item) =>
      pathname === item.path || (item.path !== "/" && pathname.startsWith(item.path))
  );
  if (match?.name) return match.name;
  for (const [prefix, title] of Object.entries(PATH_TITLES)) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) return title;
  }
  return "Workspace";
}
