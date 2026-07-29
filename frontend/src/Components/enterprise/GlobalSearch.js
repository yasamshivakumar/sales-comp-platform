import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Dialog,
  DialogContent,
  InputAdornment,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { getMenuItems, PATH_TITLES } from "../layout/navConfig";
import "./globalSearch.css";

const SHORTCUT = typeof navigator !== "undefined" && navigator.platform?.includes("Mac") ? "⌘K" : "Ctrl+K";

export default function GlobalSearch({ profile, compact = false }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef(null);

  const destinations = useMemo(() => {
    const fromMenu = getMenuItems(profile).map((i) => ({
      id: i.path,
      label: i.name,
      path: i.path,
      Icon: i.icon,
      group: "Navigate",
    }));
    const extras = Object.entries(PATH_TITLES)
      .filter(([p]) => !fromMenu.some((d) => d.path === p))
      .map(([p, l]) => ({ id: p, label: l, path: p, Icon: null, group: "More" }));
    return [...fromMenu, ...extras];
  }, [profile]);

  const results = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return destinations.slice(0, 8);
    return destinations
      .filter((d) => d.label.toLowerCase().includes(t) || d.path.toLowerCase().includes(t))
      .slice(0, 12);
  }, [destinations, q]);

  const openSearch = useCallback(() => {
    setOpen(true);
    setQ("");
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openSearch();
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openSearch]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [open]);

  const go = (path) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <>
      {compact ? (
        <button type="button" className="ent-global-search-btn" onClick={openSearch} aria-label="Search">
          <SearchIcon fontSize="small" />
        </button>
      ) : (
        <button type="button" className="ent-global-search-trigger" onClick={openSearch}>
          <SearchIcon fontSize="small" />
          <span>Search Incentra…</span>
          <kbd>{SHORTCUT}</kbd>
        </button>
      )}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
        PaperProps={{ className: "ent-global-search-dialog" }}
      >
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ p: 2, pb: 1 }}>
            <TextField
              fullWidth
              inputRef={inputRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Go to a page, module, or workspace…"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" color="action" />
                  </InputAdornment>
                ),
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && results[0]) go(results[0].path);
              }}
            />
          </Box>
          <List dense sx={{ maxHeight: 360, overflow: "auto", pb: 1 }}>
            {results.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ px: 3, py: 2 }}>
                No matches for &quot;{q}&quot;
              </Typography>
            ) : (
              results.map((item) => (
                <ListItemButton key={item.id} onClick={() => go(item.path)}>
                  {item.Icon ? (
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      <item.Icon fontSize="small" />
                    </ListItemIcon>
                  ) : null}
                  <ListItemText
                    primary={item.label}
                    secondary={item.path}
                    primaryTypographyProps={{ fontWeight: 650, fontSize: 14 }}
                    secondaryTypographyProps={{ fontSize: 12 }}
                  />
                </ListItemButton>
              ))
            )}
          </List>
        </DialogContent>
      </Dialog>
    </>
  );
}
