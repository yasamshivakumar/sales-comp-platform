import { Box, Button, Stack, Typography } from "@mui/material";
import InboxOutlinedIcon from "@mui/icons-material/InboxOutlined";

export default function EmptyState({
  title = "Nothing here yet",
  description,
  icon: Icon = InboxOutlinedIcon,
  action,
  actionLabel,
  onAction,
  compact = false,
}) {
  return (
    <Box className={`ent-empty${compact ? " ent-empty--compact" : ""}`} role="status">
      <span className="ent-empty__icon" aria-hidden>
        <Icon fontSize="large" />
      </span>
      <Typography variant="h3" component="h2" className="ent-empty__title">
        {title}
      </Typography>
      {description ? (
        <Typography variant="body2" color="text.secondary" className="ent-empty__desc">
          {description}
        </Typography>
      ) : null}
      {action || (actionLabel && onAction) ? (
        <Stack direction="row" spacing={1} sx={{ mt: 2 }} justifyContent="center">
          {action || (
            <Button variant="contained" onClick={onAction}>
              {actionLabel}
            </Button>
          )}
        </Stack>
      ) : null}
    </Box>
  );
}
