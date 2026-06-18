import { ThemeProvider as MuiProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { useMemo } from "react";
import { useTheme } from "../ThemeContext";
import { buildMuiTheme } from "../theme/muiTheme";

export default function MuiThemeProvider({ children }) {
  const { isDarkMode } = useTheme();
  const theme = useMemo(
    () => buildMuiTheme(isDarkMode ? "dark" : "light"),
    [isDarkMode]
  );

  return (
    <MuiProvider theme={theme}>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <CssBaseline />
        {children}
      </LocalizationProvider>
    </MuiProvider>
  );
}
