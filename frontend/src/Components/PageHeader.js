import { Box, Chip, Stack, Typography } from "@mui/material";

function PageHeader({ title, subtitle, badge, children }) {
  return (
    <Box
      sx={{
        mb: 3,
        pb: 2.5,
        borderBottom: "1px solid",
        borderColor: "divider",
      }}
    >
      <Stack
        direction={{ xs: "column", md: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", md: "flex-end" }}
        spacing={2}
      >
        <Box>
          {badge && (
            <Chip
              label={badge.toUpperCase()}
              size="small"
              sx={{
                mb: 1,
                height: 22,
                fontWeight: 700,
                letterSpacing: "0.08em",
                bgcolor: "primary.main",
                color: "primary.contrastText",
                "& .MuiChip-label": { px: 1.25 },
              }}
            />
          )}
          <Typography variant="h1" component="h1" sx={{ mb: subtitle ? 0.5 : 0 }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 720 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {children && (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ pt: { md: 0.5 } }}>
            {children}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

export default PageHeader;
