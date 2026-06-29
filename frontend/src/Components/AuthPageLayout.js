import { Box, Grid, Typography } from "@mui/material";
import { enterprise } from "../theme/muiTheme";

export const authFormCardSx = {
  width: "100%",
  maxWidth: 440,
  borderRadius: 2.5,
  p: { xs: 2.5, sm: 3 },
  boxShadow: "0 16px 48px rgba(3, 45, 96, 0.14)",
  border: "1px solid rgba(255, 255, 255, 0.85)",
  bgcolor: "background.paper",
};

const pageBg = {
  minHeight: "100vh",
  background: `
    radial-gradient(ellipse 80% 60% at 10% 0%, rgba(1, 118, 211, 0.12) 0%, transparent 55%),
    radial-gradient(ellipse 70% 50% at 90% 100%, rgba(3, 45, 96, 0.1) 0%, transparent 50%),
    linear-gradient(165deg, #e4ecf6 0%, #dce8f4 40%, #d4e3f2 100%)
  `,
};

const brandPanelSx = {
  display: { xs: "none", md: "flex" },
  flexDirection: "column",
  justifyContent: "center",
  px: 6,
  position: "relative",
  overflow: "hidden",
  background: `linear-gradient(165deg, ${enterprise.navy} 0%, ${enterprise.navyDark} 52%, #00122e 100%)`,
  color: "#fff",
  "&::before": {
    content: '""',
    position: "absolute",
    top: -100,
    right: -60,
    width: 340,
    height: 340,
    borderRadius: "50%",
    background: "rgba(1, 118, 211, 0.18)",
    pointerEvents: "none",
  },
  "&::after": {
    content: '""',
    position: "absolute",
    bottom: -80,
    left: -40,
    width: 260,
    height: 260,
    borderRadius: "50%",
    background: "rgba(255, 255, 255, 0.04)",
    pointerEvents: "none",
  },
};

const mobileBrandSx = {
  display: { xs: "flex", md: "none" },
  alignItems: "center",
  gap: 1.5,
  py: 2,
  px: 2.5,
  width: "100%",
  flexShrink: 0,
  background: `linear-gradient(135deg, ${enterprise.navy} 0%, ${enterprise.navyDark} 100%)`,
  color: "#fff",
  boxShadow: "0 4px 20px rgba(3, 45, 96, 0.2)",
};

function AuthPageLayout({ brand, children }) {
  return (
    <Grid container sx={pageBg}>
      <Grid item xs={false} md={5} sx={brandPanelSx}>
        <Box sx={{ maxWidth: 380, position: "relative", zIndex: 1 }}>{brand}</Box>
      </Grid>

      <Grid
        item
        xs={12}
        md={7}
        sx={{
          display: "flex",
          flexDirection: "column",
          minHeight: { xs: "100vh", md: "auto" },
        }}
      >
        <Box sx={mobileBrandSx}>
          <Box
            component="img"
            src="/incentra-icon.svg"
            alt="Incentra"
            sx={{
              width: 40,
              height: 40,
              borderRadius: 1.5,
              boxShadow: "0 4px 12px rgba(1,118,211,0.35)",
            }}
          />
          <Typography fontWeight={800} letterSpacing="-0.02em">
            Incentra
          </Typography>
        </Box>

        <Box
          sx={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            p: { xs: 2, sm: 4 },
            pb: { xs: 4, sm: 4 },
          }}
        >
          {children}
        </Box>
      </Grid>
    </Grid>
  );
}

export default AuthPageLayout;
