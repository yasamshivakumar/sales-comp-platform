import { Box, Grid, Typography } from "@mui/material";
import { enterprise } from "../theme/muiTheme";

export const authFormCardSx = {
  width: "100%",
  maxWidth: 440,
  borderRadius: 3.5,
  p: { xs: 2.5, sm: 3 },
  boxShadow: "0 20px 60px rgba(3, 45, 96, 0.18)",
  border: "1px solid rgba(255, 255, 255, 0.45)",
  bgcolor: "rgba(255, 255, 255, 0.55)",
  backdropFilter: "blur(18px) saturate(1.25)",
  WebkitBackdropFilter: "blur(18px) saturate(1.25)",
};

const pageBg = {
  minHeight: "100vh",
  background: `
    radial-gradient(ellipse 70% 55% at 12% 18%, rgba(27, 150, 255, 0.28) 0%, transparent 55%),
    radial-gradient(ellipse 55% 45% at 88% 82%, rgba(1, 118, 211, 0.22) 0%, transparent 50%),
    linear-gradient(165deg, #d7e6f6 0%, #c5daf0 45%, #a8c8e8 100%)
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
