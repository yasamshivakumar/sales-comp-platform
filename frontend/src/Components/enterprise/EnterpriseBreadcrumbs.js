import { Link as RouterLink } from "react-router-dom";
import { Breadcrumbs as MuiBreadcrumbs, Link, Typography } from "@mui/material";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";

export default function EnterpriseBreadcrumbs({ items = [], sx }) {
  if (!items.length) return null;
  return (
    <MuiBreadcrumbs
      separator={<NavigateNextIcon fontSize="small" sx={{ opacity: 0.55 }} />}
      aria-label="Breadcrumb"
      className="ent-breadcrumbs"
      sx={{ mb: 1, ...sx }}
    >
      {items.map((item, index) => {
        const last = index === items.length - 1;
        if (last || !item.to) {
          return (
            <Typography
              key={`${item.label}-${index}`}
              variant="caption"
              color="text.secondary"
              fontWeight={last ? 700 : 500}
              sx={{ letterSpacing: "0.02em" }}
            >
              {item.label}
            </Typography>
          );
        }
        return (
          <Link
            key={`${item.label}-${index}`}
            component={RouterLink}
            to={item.to}
            underline="hover"
            color="text.secondary"
            variant="caption"
            fontWeight={600}
          >
            {item.label}
          </Link>
        );
      })}
    </MuiBreadcrumbs>
  );
}
