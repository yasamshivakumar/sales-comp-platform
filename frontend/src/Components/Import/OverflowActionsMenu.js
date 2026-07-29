import { useState } from "react";
import { IconButton, ListItemIcon, ListItemText, Menu, MenuItem, Tooltip } from "@mui/material";
import MoreVertIcon from "@mui/icons-material/MoreVert";

/**
 * Three-dot (kebab) overflow menu for contextual actions beside a primary CTA.
 *
 * items: [{ id, label, icon?, onClick, disabled? }]
 */
export default function OverflowActionsMenu({
  items = [],
  ariaLabel = "More actions",
  size = "medium",
}) {
  const [anchor, setAnchor] = useState(null);
  const open = Boolean(anchor);

  const close = () => setAnchor(null);

  return (
    <>
      <Tooltip title={ariaLabel}>
        <IconButton
          aria-label={ariaLabel}
          aria-haspopup="menu"
          aria-expanded={open ? "true" : undefined}
          aria-controls={open ? "overflow-actions-menu" : undefined}
          onClick={(e) => setAnchor(e.currentTarget)}
          size={size}
          className="imp-overflow-btn"
        >
          <MoreVertIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu
        id="overflow-actions-menu"
        anchorEl={anchor}
        open={open}
        onClose={close}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { className: "imp-overflow-menu" } }}
      >
        {items.map((item) => (
          <MenuItem
            key={item.id}
            disabled={item.disabled}
            onClick={() => {
              close();
              item.onClick?.();
            }}
          >
            {item.icon ? <ListItemIcon>{item.icon}</ListItemIcon> : null}
            <ListItemText>{item.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
